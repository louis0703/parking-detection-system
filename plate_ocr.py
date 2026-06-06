"""
车牌字符识别模块
使用 RapidOCR（基于 PaddleOCR 模型的 ONNX 推理）进行车牌字符识别
保留 ddddocr 作为备选方案
"""

import cv2
import numpy as np
import os


# ============================================================
# OCR 引擎初始化（懒加载）
# ============================================================

_rapid_ocr = None
_dddd_ocr = None


def get_rapid_ocr():
    """获取 RapidOCR 实例（懒加载）"""
    global _rapid_ocr
    if _rapid_ocr is None:
        from rapidocr_onnxruntime import RapidOCR
        _rapid_ocr = RapidOCR()
    return _rapid_ocr


def get_dddd_ocr():
    """获取 ddddocr 实例（懒加载，备选方案）"""
    global _dddd_ocr
    if _dddd_ocr is None:
        import ddddocr
        _dddd_ocr = ddddocr.DdddOcr(show_ad=False)
    return _dddd_ocr


# ============================================================
# 车牌文本后处理
# ============================================================

# 省份字符常见误识别映射表
_PROVINCE_CORRECTIONS = {
    '就': '京',   # 京 常被误认为 就
}

# 字符级常见纠错映射（车牌中 I/O 不使用，容易和 1/0 混淆）
_CHAR_CORRECTIONS = {
    'i': '1',  # i -> 1
    'I': '1',  # I -> 1
    'o': '0',  # o -> 0
    'O': '0',  # O -> 0
    'l': '1',  # l (小写L) -> 1
}

# 所有合法省份简称
PROVINCES = '京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤川青藏琼宁'

# 车牌中不使用的字母（容易与数字混淆）
_PLATE_UNUSED_LETTERS = set('IO')


def _correct_province(text):
    """
    纠正省份字符的常见误识别
    如果第一个字符不是合法省份，尝试根据误识别映射表纠正
    """
    if not text or len(text) < 2:
        return text

    first_char = text[0]

    # 已经是合法省份，无需纠正
    if first_char in PROVINCES:
        return text

    # 尝试从映射表纠正
    if first_char in _PROVINCE_CORRECTIONS:
        return _PROVINCE_CORRECTIONS[first_char] + text[1:]

    return text


def _normalize_plate_text(text):
    """
    车牌文本标准化：
    1. 去除分隔符（中间点 · 等）
    2. 省份字符纠错
    3. 第2位字母大写化
    4. 第3-7位常见字符纠错（i->1, o->0 等）+ 大写
    """
    if not text:
        return text

    # 1. 去除常见分隔符
    for sep in ['·', '.', '-', ' ', '—', '‐']:
        text = text.replace(sep, '')

    # 2. 省份纠错
    text = _correct_province(text)

    # 3. 转为列表方便逐位修改
    chars = list(text)

    # 4. 第2位：字母大写
    if len(chars) > 1 and chars[1].isalpha():
        chars[1] = chars[1].upper()

    # 5. 第3-7位：纠错 + 大写
    for i in range(2, min(len(chars), 7)):
        c = chars[i]
        if c in _CHAR_CORRECTIONS:
            chars[i] = _CHAR_CORRECTIONS[c]
        elif c.isalpha():
            chars[i] = c.upper()

    return ''.join(chars)


def _score_plate_text(text):
    """
    对车牌识别结果进行评分
    中国车牌格式：省份简称(1位) + 字母(1位) + 5位字母数字
    总长度标准为 7 位
    """
    if not text:
        return 0

    score = 0
    length = len(text)

    # 长度评分：7位最佳
    if length == 7:
        score += 100
    elif length == 6:
        score += 60
    elif length == 5:
        score += 30
    elif length > 7:
        score += 40
    else:
        score += 10

    # 第一个字符应该是省份汉字
    if length > 0 and text[0] in PROVINCES:
        score += 50

    # 第二个字符应该是字母
    if length > 1 and text[1].isalpha():
        score += 20

    # 后续字符应该是字母或数字
    for i in range(2, min(length, 7)):
        if text[i].isalnum():
            score += 5

    # 包含常见误识别字符扣分
    for ch in text[2:]:
        if ch in _PLATE_UNUSED_LETTERS:
            score -= 10

    return score


# ============================================================
# 识别函数
# ============================================================

def recognize_plate(plate_image, full_image=None, plate_region=None):
    """
    识别车牌字符（简单版本）

    参数:
        plate_image: 车牌区域图像（BGR 或灰度，用于备选识别）
        full_image: 完整原始图像（可选，用于 RapidOCR 全图识别）
        plate_region: 车牌区域坐标 (x, y, w, h)（可选，用于过滤全图识别结果）

    返回:
        识别出的车牌字符串
    """
    result, _ = recognize_plate_with_confidence(plate_image, full_image, plate_region)
    return result


def recognize_plate_with_confidence(plate_image, full_image=None, plate_region=None):
    """
    识别车牌字符，返回置信度
    优先使用 RapidOCR 全图识别 + 区域匹配，ddddocr 作为备选

    参数:
        plate_image: 车牌区域图像（BGR 或灰度）
        full_image: 完整原始图像（可选，RapidOCR 在全图上效果更好）
        plate_region: 车牌区域坐标 (x, y, w, h)（可选）

    返回:
        (识别结果字符串, 置信度分数)
    """
    candidates = []

    # ---- RapidOCR 全图识别（推荐方式）----
    if full_image is not None:
        rapid = get_rapid_ocr()
        result, _ = rapid(full_image)
        if result:
            # 根据 plate_region 过滤，找到落在车牌区域内的文本
            if plate_region:
                rx, ry, rw, rh = plate_region
                # 扩大一点容差（20%）
                margin_x = rw * 0.2
                margin_y = rh * 0.2
                for line in result:
                    box, text, conf = line
                    # 计算文本中心点
                    xs = [p[0] for p in box]
                    ys = [p[1] for p in box]
                    cx = sum(xs) / 4
                    cy = sum(ys) / 4
                    # 检查是否在车牌区域内（含容差）
                    if (rx - margin_x <= cx <= rx + rw + margin_x and
                            ry - margin_y <= cy <= ry + rh + margin_y):
                        candidates.append(('rapidocr_full', text, float(conf)))
            else:
                # 没有区域信息，取置信度最高的
                best = max(result, key=lambda x: x[2])
                candidates.append(('rapidocr_full', best[1], float(best[2])))

    # ---- RapidOCR 裁剪图识别（备选）----
    if not candidates:
        rapid = get_rapid_ocr()
        result1 = _rapid_ocr_recognize(rapid, plate_image)
        if result1:
            candidates.append(result1)

    # ---- ddddocr 备选识别（当 RapidOCR 没有结果时）----
    if not candidates:
        try:
            dddd = get_dddd_ocr()
            if len(plate_image.shape) == 3:
                gray = cv2.cvtColor(plate_image, cv2.COLOR_BGR2GRAY)
            else:
                gray = plate_image.copy()
            _, img_bytes = cv2.imencode('.png', gray)
            text = dddd.classification(img_bytes.tobytes())
            if text:
                candidates.append(('ddddocr', text, 0.5))
        except Exception:
            pass

    if not candidates:
        return '', 0

    # 对所有候选结果标准化后评分，选择最佳
    scored = []
    for method, raw_text, conf in candidates:
        normalized = _normalize_plate_text(raw_text)
        score = _score_plate_text(normalized)
        scored.append((method, raw_text, normalized, conf, score))

    scored.sort(key=lambda x: x[4], reverse=True)

    # Debug info
    print(f"    OCR candidates:")
    for method, raw_text, normalized, conf, score in scored:
        marker = " *" if score == scored[0][4] else ""
        print(f"      {method:14s} -> '{raw_text}' -> '{normalized}' "
              f"(conf={conf:.3f}, score={score}){marker}")

    best = scored[0]
    best_text = best[2]  # normalized text
    best_score = best[4]

    return best_text, best_score


def _rapid_ocr_recognize(rapid, image):
    """
    使用 RapidOCR 识别单张图像

    参数:
        rapid: RapidOCR 实例
        image: BGR 或灰度图像

    返回:
        (method_name, text, confidence) 或 None
    """
    # RapidOCR 接受 BGR numpy array 或文件路径
    if len(image.shape) == 2:
        # 灰度图转 BGR
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

    result, _ = rapid(image)

    if not result:
        return None

    # RapidOCR 返回 [[box, text, confidence], ...]
    # 对于车牌，通常只有一个文本区域
    # 如果有多个，取置信度最高的
    best = max(result, key=lambda x: x[2])
    text = best[1]
    confidence = float(best[2])

    return ('rapidocr', text, confidence)


# ============================================================
# 结果保存
# ============================================================

def save_results_to_txt(results, output_path):
    """
    将识别结果保存到 txt 文件

    参数:
        results: list of dict, 每个 dict 包含:
            - image_name: 图片文件名
            - plate_regions: list of (x, y, w, h)
            - recognized_texts: list of 识别结果字符串
        output_path: 输出文件路径
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("=" * 50 + "\n")
        f.write("  车牌识别结果汇总\n")
        f.write("=" * 50 + "\n\n")

        for item in results:
            f.write(f"图片: {item['image_name']}\n")
            f.write(f"-" * 40 + "\n")

            if item['plate_regions']:
                for i, (region, text) in enumerate(
                    zip(item['plate_regions'], item['recognized_texts'])
                ):
                    x, y, w, h = region
                    f.write(f"  车牌 {i+1}:\n")
                    f.write(f"    区域: ({x}, {y}, {w}, {h})\n")
                    f.write(f"    识别结果: {text}\n")
            else:
                f.write("  未检测到车牌区域\n")

            f.write("\n")

        f.write("=" * 50 + "\n")
        f.write(f"共处理 {len(results)} 张图片\n")

        # 统计成功识别的数量
        total_plates = sum(len(r['recognized_texts']) for r in results)
        successful = sum(
            1 for r in results
            for t in r['recognized_texts']
            if t and len(t) >= 5  # 车牌至少5个字符
        )
        f.write(f"检测到 {total_plates} 个车牌区域\n")
        f.write(f"成功识别 {successful} 个车牌\n")
        f.write("=" * 50 + "\n")

    print(f"  Results saved to: {output_path}")
