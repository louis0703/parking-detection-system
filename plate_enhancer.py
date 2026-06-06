"""
车牌区域增强模块
包含：车牌定位、频域增强、对比度增强、锐化处理
"""

import cv2
import numpy as np
import os
from utils import save_result, show_comparison, calc_psnr, calc_contrast
from freq_filter import (
    dft_process, apply_freq_filter,
    gaussian_lowpass_filter, high_frequency_emphasis_filter,
    compare_freq_filters
)


# ============================================================
# 车牌定位
# ============================================================

def locate_plate_by_color(image, save_dir=None):
    """
    基于颜色空间的车牌定位
    支持蓝色车牌和黄色车牌
    """
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    results = []

    # 蓝色车牌范围（中国蓝牌：H=100~125, S>80, V>80）
    # 收紧S和V范围，减少误检
    lower_blue = np.array([100, 80, 80])
    upper_blue = np.array([125, 255, 255])
    mask_blue = cv2.inRange(hsv, lower_blue, upper_blue)

    # 黄色车牌范围
    lower_yellow = np.array([15, 80, 80])
    upper_yellow = np.array([35, 255, 255])
    mask_yellow = cv2.inRange(hsv, lower_yellow, upper_yellow)

    # 合并颜色掩膜
    mask = cv2.bitwise_or(mask_blue, mask_yellow)

    if save_dir:
        save_result(mask_blue, save_dir, "plate_mask_blue.png")
        save_result(mask, save_dir, "plate_mask_combined.png")

    # 形态学处理：先膨胀连接字符，再闭运算填充
    kernel_dilate = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    dilated = cv2.dilate(mask, kernel_dilate, iterations=2)
    kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 5))
    closed = cv2.morphologyEx(dilated, cv2.MORPH_CLOSE, kernel_close)

    if save_dir:
        save_result(closed, save_dir, "plate_mask_morphology.png")

    # 查找轮廓
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    img_h, img_w = image.shape[:2]
    candidates = []

    img_area = img_h * img_w
    # 根据图像尺寸动态计算最小面积（至少占图像的 0.1%）
    min_area = max(2000, img_area * 0.001)

    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        # 筛选条件：
        # 1. 长宽比约 2.5:1 ~ 4.5:1（车牌标准比例约 440mm x 140mm ≈ 3.14:1）
        # 2. 面积根据图像大小动态调整
        # 3. 不能太大（不超过图像面积的5%）
        # 4. 高度至少50像素，宽度至少120像素
        aspect_ratio = w / h if h > 0 else 0
        area = w * h
        if (2.5 < aspect_ratio < 4.5 and
            area > min_area and
            area < img_area * 0.05 and
            h > 50 and w > 120):
            # 计算评分：
            # 1. 越接近标准比例(3.14)越好
            # 2. 位置越靠下越好（车牌通常在图像下半部分）
            # 3. 面积适中（不要太大的挡风玻璃区域）
            ratio_score = 1 - abs(aspect_ratio - 3.14) / 3.14
            # 位置评分：y坐标越大（越靠下）分数越高，但排除最底部10%（可能是水印）
            pos_norm = (y + h) / img_h
            position_score = pos_norm if pos_norm < 0.9 else 0.5
            # 面积惩罚：面积过大扣分（挡风玻璃通常很大）
            area_ratio = area / img_area
            area_penalty = 1.0 if area_ratio < 0.02 else 0.6
            score = ratio_score * position_score * area_penalty * area
            candidates.append((x, y, w, h, score))

    # 按评分排序，返回最佳候选
    candidates.sort(key=lambda c: c[4], reverse=True)
    results = [(x, y, w, h) for x, y, w, h, _ in candidates]

    return results, mask


def locate_plate_by_edge(image, save_dir=None):
    """
    基于边缘检测的车牌定位
    """
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    # 高斯滤波
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Canny边缘检测
    edges = cv2.Canny(blurred, 100, 200)

    # 形态学闭运算连接边缘
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 5))
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)

    if save_dir:
        save_result(edges, save_dir, "plate_edge_detection.png")
        save_result(closed, save_dir, "plate_edge_closed.png")

    # 查找轮廓
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        aspect_ratio = w / h if h > 0 else 0
        area = w * h
        if 2.5 < aspect_ratio < 6.0 and area > 1000:
            candidates.append((x, y, w, h))

    return candidates


def locate_plate(image, save_dir=None):
    """
    综合定位车牌：结合颜色和边缘方法
    """
    # 方法1：颜色定位
    color_results, color_mask = locate_plate_by_color(image, save_dir)

    # 方法2：边缘定位
    edge_results = locate_plate_by_edge(image, save_dir)

    # 合并结果：优先颜色定位，其次边缘定位
    if color_results:
        all_results = color_results
        print(f"  Color detection: {len(color_results)} candidates")
    elif edge_results:
        all_results = edge_results
        print(f"  Edge detection: {len(edge_results)} candidates")
    else:
        all_results = []
        print("  No plate region detected")

    if save_dir:
        save_result(color_mask, save_dir, "plate_color_mask.png")

        # 在原图上只画最佳候选（评分最高的第一个）
        result_img = image.copy()
        if all_results:
            x, y, w, h = all_results[0]
            cv2.rectangle(result_img, (x, y), (x+w, y+h), (0, 255, 0), 3)
            cv2.putText(result_img, "Plate", (x, y-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        save_result(result_img, save_dir, "plate_detection_result.png")

    return all_results


# ============================================================
# 车牌区域增强
# ============================================================

def enhance_plate_contrast(plate_gray):
    """CLAHE对比度增强"""
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(plate_gray)
    return enhanced


def enhance_plate_sharpen(plate):
    """Unsharp Masking锐化增强"""
    blurred = cv2.GaussianBlur(plate, (0, 0), 3)
    sharpened = cv2.addWeighted(plate, 1.5, blurred, -0.5, 0)
    return sharpened


def enhance_plate_denoise(plate):
    """中值滤波去噪"""
    denoised = cv2.medianBlur(plate, 3)
    return denoised


def enhance_plate_full(plate_gray, save_dir=None):
    """
    完整的车牌增强流程：
    1. 去噪
    2. CLAHE对比度增强
    3. 高频增强滤波（频域锐化）
    4. Unsharp Masking锐化
    """
    results = {}

    # 0. 原始
    results['original'] = plate_gray.copy()
    if save_dir:
        save_result(plate_gray, save_dir, "plate_original.png")

    # 1. 中值滤波去噪
    denoised = enhance_plate_denoise(plate_gray)
    results['denoised'] = denoised
    if save_dir:
        save_result(denoised, save_dir, "plate_denoised.png")

    # 2. CLAHE对比度增强
    contrast_enhanced = enhance_plate_contrast(denoised)
    results['contrast_enhanced'] = contrast_enhanced
    if save_dir:
        save_result(contrast_enhanced, save_dir, "plate_contrast_enhanced.png")

    # 3. 高频增强滤波（频域）
    hfe = high_frequency_emphasis_filter(plate_gray.shape, cutoff=30, a=0.5, b=1.5)
    freq_enhanced = apply_freq_filter(plate_gray, hfe)
    results['freq_enhanced'] = freq_enhanced
    if save_dir:
        save_result(freq_enhanced, save_dir, "plate_freq_enhanced.png")

    # 4. Unsharp Masking锐化
    sharpened = enhance_plate_sharpen(contrast_enhanced)
    results['sharpened'] = sharpened
    if save_dir:
        save_result(sharpened, save_dir, "plate_sharpened.png")

    # 对比展示
    if save_dir:
        show_comparison(
            [plate_gray, denoised, contrast_enhanced, sharpened],
            ["Original", "Denoised", "CLAHE Enhanced", "Sharpened"],
            save_path=os.path.join(save_dir, "plate_enhancement_comparison.png")
        )

        # 频域增强对比
        show_comparison(
            [plate_gray, freq_enhanced],
            ["Original", "High Freq Emphasis"],
            save_path=os.path.join(save_dir, "plate_freq_comparison.png")
        )

    return results


# ============================================================
# 频域滤波器对比（车牌场景）
# ============================================================

def compare_plate_freq_filters(plate_gray, save_dir=None):
    """对比不同频域滤波器对车牌的增强效果"""
    shape = plate_gray.shape

    cutoff = 30

    # 各种滤波器
    H_ideal = gaussian_lowpass_filter(shape, cutoff)  # 用高斯作为理想低通的平滑版本
    H_hfe = high_frequency_emphasis_filter(shape, cutoff)

    result_lpf = apply_freq_filter(plate_gray, H_ideal)
    result_hfe = apply_freq_filter(plate_gray, H_hfe)

    if save_dir:
        save_result(result_lpf, save_dir, "plate_gaussian_lpf.png")
        save_result(result_hfe, save_dir, "plate_hfe.png")

        show_comparison(
            [plate_gray, result_lpf, result_hfe],
            ["Original", "Gaussian LPF", "High Freq Emphasis"],
            save_path=os.path.join(save_dir, "plate_freq_filter_comparison.png")
        )

    return result_lpf, result_hfe


# ============================================================
# 主增强流程
# ============================================================

def run_plate_enhancement(image_path, save_dir=None):
    """
    运行完整的车牌增强流程

    参数:
        image_path: 图像路径
        save_dir: 结果保存目录
    """
    image = cv2.imread(image_path)
    if image is None:
        print(f"Failed to read image: {image_path}")
        return None

    # 1. 车牌定位
    plate_regions = locate_plate(image, save_dir)

    if not plate_regions:
        print("No plate region detected")
        return None

    enhanced_plates = []

    for i, (x, y, w, h) in enumerate(plate_regions):
        plate_roi = image[y:y+h, x:x+w]
        plate_gray = cv2.cvtColor(plate_roi, cv2.COLOR_BGR2GRAY)

        plate_save_dir = os.path.join(save_dir, f"plate_{i}") if save_dir else None
        if plate_save_dir:
            os.makedirs(plate_save_dir, exist_ok=True)
            # 保存检测到的车牌区域
            save_result(plate_roi, plate_save_dir, "detected_plate.png")

        # 2. 增强处理
        results = enhance_plate_full(plate_gray, plate_save_dir)

        # 3. 频域滤波器对比
        if plate_save_dir:
            compare_plate_freq_filters(plate_gray, plate_save_dir)

        # 4. 计算PSNR和对比度
        psnr = calc_psnr(plate_gray, results['sharpened'])
        contrast_before = calc_contrast(plate_gray)
        contrast_after = calc_contrast(results['sharpened'])

        print(f"Plate {i}: PSNR={psnr:.2f}dB, "
              f"Contrast: {contrast_before:.2f} -> {contrast_after:.2f}")

        enhanced_plates.append({
            'region': (x, y, w, h),
            'original': plate_gray,
            'enhanced': results['sharpened'],
            'psnr': psnr,
            'contrast_before': contrast_before,
            'contrast_after': contrast_after
        })

    return enhanced_plates
