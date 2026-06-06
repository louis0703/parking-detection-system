"""
停车位占用检测与车牌区域增强系统
主程序入口 - 处理真实测试图片
"""

import cv2
import numpy as np
import os
import sys

from parking_detector import (
    preprocessing, edge_detection, segmentation, morphology,
    detect_parking_occupancy
)
from plate_enhancer import (
    enhance_plate_full, compare_plate_freq_filters, locate_plate
)
from plate_ocr import recognize_plate, recognize_plate_with_confidence, save_results_to_txt
from freq_filter import compare_freq_filters
from utils import save_result, show_comparison, mark_parking_spots, calc_psnr, calc_contrast


def process_parking_image(image_path, save_dir):
    """处理单张停车场图片：完整流程"""
    print(f"\n{'='*60}")
    print(f"Processing parking image: {os.path.basename(image_path)}")
    print(f"{'='*60}")

    image = cv2.imread(image_path)
    if image is None:
        print(f"  Failed to read: {image_path}")
        return

    h, w = image.shape[:2]
    print(f"  Image size: {w}x{h}")

    # 创建子目录
    prep_dir = os.path.join(save_dir, "preprocessing")
    edge_dir = os.path.join(save_dir, "edge_detection")
    seg_dir = os.path.join(save_dir, "segmentation")
    morph_dir = os.path.join(save_dir, "morphology")
    freq_dir = os.path.join(save_dir, "frequency")
    final_dir = os.path.join(save_dir, "final")
    for d in [prep_dir, edge_dir, seg_dir, morph_dir, freq_dir, final_dir]:
        os.makedirs(d, exist_ok=True)

    # 保存原始图像
    save_result(image, save_dir, "original.png")

    # ========== 1. 图像预处理 ==========
    print("  [1/6] Preprocessing...")
    prep = preprocessing(image, prep_dir)

    # ========== 2. 边缘检测 ==========
    print("  [2/6] Edge detection...")
    edges = edge_detection(prep['gaussian_blur'], edge_dir)

    # ========== 3. 图像分割 ==========
    print("  [3/6] Segmentation...")
    seg = segmentation(prep['gaussian_blur'], seg_dir)

    # ========== 4. 形态学处理 ==========
    print("  [4/6] Morphology...")
    morph = morphology(seg['binary_otsu'], morph_dir)

    # ========== 5. 频域处理 ==========
    print("  [5/6] Frequency domain...")
    compare_freq_filters(prep['gaussian_blur'], freq_dir)

    # ========== 6. 车位状态判断 ==========
    print("  [6/6] Occupancy detection...")

    # 检测地面白色线条来定位车位区域
    gray = prep['gaussian_blur']

    # 用Canny检测线条
    edges_canny = cv2.Canny(gray, 50, 150)

    # 用霍夫变换检测直线
    lines = cv2.HoughLinesP(edges_canny, 1, np.pi/180, 50,
                            minLineLength=100, maxLineGap=10)

    # 在原图上画出检测到的线条
    line_img = image.copy()
    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            cv2.line(line_img, (x1, y1), (x2, y2), (0, 255, 0), 2)
    save_result(line_img, final_dir, "detected_lines.png")

    # ========== 车位区域分析 ==========
    # 方法：基于连通域分析检测车位上的大型固体物体
    # 核心思路：地面变化（网格草缝、阴影）产生小而分散的连通域，
    #           而实际物体（车辆、施工材料）产生大而连续的连通域

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    # 1. 检测黄/白车位线并保存
    lower_yellow = np.array([15, 80, 80])
    upper_yellow = np.array([35, 255, 255])
    yellow_mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
    lower_white = np.array([0, 0, 150])
    upper_white = np.array([180, 50, 255])
    white_mask = cv2.inRange(hsv, lower_white, upper_white)
    line_mask = cv2.bitwise_or(yellow_mask, white_mask)
    kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 5))
    line_mask = cv2.morphologyEx(line_mask, cv2.MORPH_CLOSE, kernel_close)
    save_result(line_mask, final_dir, "white_lines_mask.png")

    # 2. 分析地面区域（取图像下半部分）
    ground_y = int(h * 0.35)
    roi = gray[ground_y:h, :]
    hsv_roi = hsv[ground_y:h, :]
    roi_area = roi.shape[0] * roi.shape[1]

    # 3. 计算地面主色调（用中位数，对异常值鲁棒）
    ground_b = float(np.median(hsv_roi[:, :, 0]))
    ground_s = float(np.median(hsv_roi[:, :, 1]))
    ground_v = float(np.median(hsv_roi[:, :, 2]))

    # 4. 检测棕色物体（木板、施工材料等）
    brown_mask = cv2.inRange(hsv_roi, np.array([10, 50, 50]), np.array([25, 255, 255]))

    # 形态学处理：连接邻近区域
    kernel_clean = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    brown_clean = cv2.morphologyEx(brown_mask, cv2.MORPH_CLOSE,
                                    cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15)))
    brown_clean = cv2.dilate(brown_clean, kernel_clean, iterations=2)

    # 5. 中心区域分析：排除边缘墙壁/围栏
    roi_h, roi_w = roi.shape[:2]
    cx_start, cx_end = int(roi_w * 0.15), int(roi_w * 0.85)
    cy_start, cy_end = int(roi_h * 0.10), int(roi_h * 0.90)
    center_mask = np.zeros_like(brown_clean)
    center_mask[cy_start:cy_end, cx_start:cx_end] = 255
    brown_center = cv2.bitwise_and(brown_clean, center_mask)
    center_roi_area = (cx_end - cx_start) * (cy_end - cy_start)

    save_result(brown_center, final_dir, "foreground_mask.png")

    # 6. 连通域分析 + 形状特征
    # 关键区别：植被是细长条状（高长宽比），物体是紧凑块状（低长宽比）
    contours, _ = cv2.findContours(brown_center, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    large_compact_objects = []
    total_fg_area = 0
    for cnt in contours:
        area = cv2.contourArea(cnt)
        total_fg_area += area
        if area > center_roi_area * 0.08:
            x, y, cw, ch = cv2.boundingRect(cnt)
            aspect = cw / ch if ch > 0 else 0
            # 紧凑物体：长宽比 < 2.5（不是细长条状）
            if aspect < 2.5:
                large_compact_objects.append((area, aspect))

    # 7. 纹理遮挡检测（检测车辆等大型均匀物体遮挡地面纹理）
    # 原理：空网格地面有高对比度（亮砖+暗洞），车辆漆面是低对比度的均匀区域
    center_gray = roi[cy_start:cy_end, cx_start:cx_end]
    block_size = 32
    cbh, cbw = center_gray.shape
    texture_mask = np.zeros((cbh // block_size, cbw // block_size), dtype=np.uint8)
    for by in range(texture_mask.shape[0]):
        for bx in range(texture_mask.shape[1]):
            block = center_gray[by*block_size:(by+1)*block_size, bx*block_size:(bx+1)*block_size]
            if float(np.max(block) - np.min(block)) < 40:
                texture_mask[by, bx] = 255

    # 形态学闭运算连接邻近的低对比度块
    kernel_texture = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    texture_mask = cv2.morphologyEx(texture_mask, cv2.MORPH_CLOSE, kernel_texture, iterations=2)

    # 连通域分析：找最大连通域
    texture_occupied = False
    texture_largest_ratio = 0
    num_text_components = 0
    center_mean_brightness = float(np.mean(center_gray))
    if cv2.countNonZero(texture_mask) > 0:
        num_labels_t, labels_t, stats_t, _ = cv2.connectedComponentsWithStats(texture_mask)
        if num_labels_t > 1:
            areas_t = stats_t[1:, cv2.CC_STAT_AREA]
            largest_t = int(np.max(areas_t))
            texture_largest_ratio = largest_t / texture_mask.size
            num_text_components = num_labels_t - 1
            # 判断：
            # - 最大连通域占中心区域 5%-40% → 可能是车
            # - 中心区域整体亮度 > 80（排除夜间暗区和室内暗地面）
            if 0.05 < texture_largest_ratio < 0.40 and center_mean_brightness > 80:
                texture_occupied = True

    # 可视化纹理掩膜：放大到中心区域大小，叠加在原图上
    texture_vis = cv2.resize(texture_mask, (cx_end - cx_start, cy_end - cy_start),
                             interpolation=cv2.INTER_NEAREST)
    roi_color = cv2.cvtColor(roi, cv2.COLOR_GRAY2BGR)
    center_region = roi_color[cy_start:cy_end, cx_start:cx_end].copy()
    # 红色半透明叠加低对比度区域
    red_overlay = center_region.copy()
    red_overlay[texture_vis > 0] = [0, 0, 255]
    center_region = cv2.addWeighted(center_region, 0.6, red_overlay, 0.4, 0)
    # 画网格线标注块边界
    for by in range(0, center_region.shape[0], block_size):
        cv2.line(center_region, (0, by), (center_region.shape[1], by), (100, 100, 100), 1)
    for bx in range(0, center_region.shape[1], block_size):
        cv2.line(center_region, (bx, 0), (bx, center_region.shape[0]), (100, 100, 100), 1)
    # 标注文字
    label_tex = "Texture: Y (car detected)" if texture_occupied else "Texture: N"
    color_tex = (0, 0, 255) if texture_occupied else (0, 255, 0)
    cv2.putText(center_region, label_tex, (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, color_tex, 2)
    cv2.putText(center_region, f"Largest: {texture_largest_ratio:.1%} Blocks: {num_text_components}",
                (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    save_result(center_region, final_dir, "texture_mask.png")

    # 8. 综合判断：棕色物体检测 OR 纹理遮挡检测
    fg_ratio = total_fg_area / center_roi_area
    largest_area = large_compact_objects[0][0] if large_compact_objects else 0
    brown_largest_ratio = largest_area / center_roi_area
    largest_aspect = large_compact_objects[0][1] if large_compact_objects else 0

    brown_occupied = len(large_compact_objects) > 0 and brown_largest_ratio > 0.10
    is_occupied = brown_occupied or texture_occupied

    status_en = "full" if is_occupied else "empty"
    print(f"  Brown detection: {'OCCUPIED' if brown_occupied else 'empty'} (largest={brown_largest_ratio:.4f})")
    print(f"  Texture detection: {'OCCUPIED' if texture_occupied else 'empty'} (largest={texture_largest_ratio:.2%}, blocks={num_text_components})")
    print(f"  Result: {'full' if is_occupied else 'empty'}")

    # 标注结果
    result = image.copy()
    color = (0, 0, 255) if is_occupied else (0, 255, 0)
    label = f"Status: {status_en}"
    cv2.putText(result, label, (10, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2)
    cv2.putText(result, f"Brown: {'Y' if brown_occupied else 'N'} Texture: {'Y' if texture_occupied else 'N'}", (10, 80),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cv2.putText(result, f"Brown largest: {brown_largest_ratio:.4f}", (10, 110),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cv2.putText(result, f"Texture largest: {texture_largest_ratio:.2%}", (10, 140),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    # 画出ROI区域和中心区域
    cv2.rectangle(result, (0, ground_y), (w, h), (255, 255, 0), 2)
    cv2.rectangle(result, (cx_start, ground_y + cy_start),
                  (cx_end, ground_y + cy_end), (255, 200, 0), 1)
    # 画出检测到的大型物体轮廓
    all_contours, _ = cv2.findContours(brown_center, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in all_contours:
        area = cv2.contourArea(cnt)
        if area > center_roi_area * 0.08:
            x_c, y_c, w_c, h_c = cv2.boundingRect(cnt)
            cv2.rectangle(result, (x_c, y_c + ground_y), (x_c + w_c, y_c + h_c + ground_y), (0, 0, 255), 2)
    save_result(result, final_dir, "parking_result.png")

    # 综合对比图
    show_comparison(
        [image, prep['clahe'], edges['canny'], seg['binary_otsu'], morph['closed'], result],
        ["Original", "CLAHE", "Canny Edge", "Otsu Segmentation", "Morphology", f"Result: {status_en}"],
        save_path=os.path.join(final_dir, "pipeline_comparison.png"),
        figsize=(20, 4)
    )

    print(f"  Results saved to: {save_dir}")
    return is_occupied


def process_plate_image(image_path, save_dir):
    """处理单张车牌图片：完整流程（含字符识别）"""
    print(f"\n{'='*60}")
    print(f"Processing plate image: {os.path.basename(image_path)}")
    print(f"{'='*60}")

    image = cv2.imread(image_path)
    if image is None:
        print(f"  Failed to read: {image_path}")
        return None

    h, w = image.shape[:2]
    print(f"  Image size: {w}x{h}")

    os.makedirs(save_dir, exist_ok=True)

    # 保存原始图像
    save_result(image, save_dir, "original.png")

    # ========== 1. 车牌定位 ==========
    print("  [1/5] Plate detection...")
    plate_regions = locate_plate(image, save_dir)

    if not plate_regions:
        print("  No plate detected, trying full image enhancement")
        # 如果没检测到，对全图做增强
        plate_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        plate_regions = [(0, 0, w, h)]

    recognized_texts = []

    # 只处理最佳候选（评分最高的第一个）
    for idx, (x, y, pw, ph) in enumerate(plate_regions[:1]):
        plate_dir = os.path.join(save_dir, f"plate_{idx}")
        os.makedirs(plate_dir, exist_ok=True)

        plate_roi = image[y:y+ph, x:x+pw]
        save_result(plate_roi, plate_dir, "detected_plate.png")

        plate_gray = cv2.cvtColor(plate_roi, cv2.COLOR_BGR2GRAY)

        # ========== 2. 图像预处理 ==========
        print(f"  [2/5] Preprocessing...")
        prep = preprocessing(plate_roi, plate_dir)

        # ========== 3. 边缘检测 ==========
        print(f"  [3/5] Edge detection...")
        edges = edge_detection(prep['gaussian_blur'], plate_dir)

        # ========== 4. 车牌增强 ==========
        print(f"  [4/5] Plate enhancement...")
        enhance_results = enhance_plate_full(plate_gray, plate_dir)

        # 频域滤波器对比
        compare_plate_freq_filters(plate_gray, plate_dir)

        # 计算增强前后对比指标
        psnr = calc_psnr(plate_gray, enhance_results['sharpened'])
        contrast_before = calc_contrast(plate_gray)
        contrast_after = calc_contrast(enhance_results['sharpened'])

        print(f"  PSNR: {psnr:.2f} dB")
        print(f"  Contrast: {contrast_before:.2f} -> {contrast_after:.2f}")

        # 综合对比图
        show_comparison(
            [plate_gray, enhance_results['denoised'],
             enhance_results['contrast_enhanced'], enhance_results['sharpened']],
            ["Original", "Denoised", "CLAHE Enhanced", "Sharpened"],
            save_path=os.path.join(plate_dir, "enhancement_pipeline.png"),
            figsize=(16, 4)
        )

        # ========== 5. 车牌字符识别 ==========
        print(f"  [5/5] OCR recognition...")
        # 使用全图识别 + 区域匹配（RapidOCR 在全图上效果远好于裁剪图）
        plate_region = plate_regions[0]  # (x, y, w, h)
        ocr_text, confidence = recognize_plate_with_confidence(
            plate_roi, full_image=image, plate_region=plate_region
        )
        recognized_texts.append(ocr_text)
        print(f"  OCR result: {ocr_text}")

        # 保存识别结果图片（在车牌上标注识别文字）
        plate_with_text = plate_roi.copy()
        cv2.putText(plate_with_text, ocr_text, (5, plate_roi.shape[0] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        save_result(plate_with_text, plate_dir, "plate_recognized.png")

    print(f"  Results saved to: {save_dir}")

    return {
        'image_name': os.path.basename(image_path),
        'plate_regions': plate_regions[:1],
        'recognized_texts': recognized_texts
    }


def main():
    """主函数：处理所有测试图片"""
    print("=" * 60)
    print("  Parking Occupancy Detection & Plate Enhancement System")
    print("=" * 60)

    # 清除旧结果
    if os.path.exists("results"):
        import shutil
        shutil.rmtree("results")

    # ========== 处理停车场图片 ==========
    parking_dir = "test_images/parking"
    if os.path.exists(parking_dir):
        parking_files = sorted([f for f in os.listdir(parking_dir)
                                if f.lower().endswith(('.jpg', '.png', '.jpeg'))])
        print(f"\nFound {len(parking_files)} parking images")

        for f in parking_files:
            img_path = os.path.join(parking_dir, f)
            save_dir = os.path.join("results", "parking", f.split('.')[0])
            process_parking_image(img_path, save_dir)

    # ========== 处理车牌图片 ==========
    plate_dir = "test_images/plates"
    ocr_results = []
    if os.path.exists(plate_dir):
        plate_files = sorted([f for f in os.listdir(plate_dir)
                              if f.lower().endswith(('.jpg', '.png', '.jpeg'))])
        print(f"\nFound {len(plate_files)} plate images")

        for f in plate_files:
            img_path = os.path.join(plate_dir, f)
            save_dir = os.path.join("results", "plates", f.split('.')[0])
            result = process_plate_image(img_path, save_dir)
            if result:
                ocr_results.append(result)

        # 保存识别结果到 txt 文件
        if ocr_results:
            txt_path = os.path.join("results", "plates", "plate_results.txt")
            save_results_to_txt(ocr_results, txt_path)

    # ========== Summary ==========
    print("\n" + "=" * 60)
    print("  All images processed!")
    print("  Results saved in results/ directory")
    print("=" * 60)

    # List generated files
    print("\nGenerated files:")
    for root, dirs, files in os.walk("results"):
        for f in sorted(files):
            if f.endswith('.png'):
                path = os.path.join(root, f)
                print(f"  {path}")


if __name__ == "__main__":
    main()
