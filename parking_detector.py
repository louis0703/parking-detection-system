"""
停车位占用检测模块
包含：图像预处理、边缘检测、图像分割、形态学处理、车位状态判断
"""

import cv2
import numpy as np
import os
from utils import save_result, show_comparison, mark_parking_spots


# ============================================================
# 第一阶段：图像预处理
# ============================================================

def preprocessing(image, save_dir=None):
    """图像预处理：灰度化 + 直方图均衡化 + 滤波去噪"""
    results = {}

    # 1. 灰度化
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    results['gray'] = gray
    if save_dir:
        save_result(gray, save_dir, "01_grayscale.png")

    # 2. 直方图均衡化
    equalized = cv2.equalizeHist(gray)
    results['equalized'] = equalized
    if save_dir:
        save_result(equalized, save_dir, "02_hist_equalized.png")

    # 3. CLAHE自适应均衡化（效果更好）
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    clahe_result = clahe.apply(gray)
    results['clahe'] = clahe_result
    if save_dir:
        save_result(clahe_result, save_dir, "03_clahe.png")

    # 4. 高斯滤波去噪
    gaussian_blur = cv2.GaussianBlur(clahe_result, (5, 5), 0)
    results['gaussian_blur'] = gaussian_blur
    if save_dir:
        save_result(gaussian_blur, save_dir, "04_gaussian_blur.png")

    # 5. 中值滤波去噪
    median_blur = cv2.medianBlur(clahe_result, 5)
    results['median_blur'] = median_blur
    if save_dir:
        save_result(median_blur, save_dir, "05_median_blur.png")

    # 预处理对比图
    if save_dir:
        show_comparison(
            [gray, equalized, clahe_result, gaussian_blur, median_blur],
            ["Original", "Hist Equal", "CLAHE", "Gaussian Blur", "Median Blur"],
            save_path=os.path.join(save_dir, "preprocessing_comparison.png")
        )

    return results


# ============================================================
# 第二阶段：边缘检测
# ============================================================

def edge_detection(gray, save_dir=None):
    """实现并对比多种边缘检测方法"""
    results = {}

    # 1. Sobel边缘检测
    sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    sobel = cv2.magnitude(sobel_x, sobel_y)
    sobel = np.uint8(np.clip(sobel, 0, 255))
    results['sobel'] = sobel
    if save_dir:
        save_result(sobel, save_dir, "sobel.png")

    # 2. Prewitt边缘检测（用自定义卷积核）
    kernel_prewitt_x = np.array([[-1, 0, 1], [-1, 0, 1], [-1, 0, 1]], dtype=np.float32)
    kernel_prewitt_y = np.array([[-1, -1, -1], [0, 0, 0], [1, 1, 1]], dtype=np.float32)
    prewitt_x = cv2.filter2D(gray, cv2.CV_64F, kernel_prewitt_x)
    prewitt_y = cv2.filter2D(gray, cv2.CV_64F, kernel_prewitt_y)
    prewitt = cv2.magnitude(prewitt_x, prewitt_y)
    prewitt = np.uint8(np.clip(prewitt, 0, 255))
    results['prewitt'] = prewitt
    if save_dir:
        save_result(prewitt, save_dir, "prewitt.png")

    # 3. Roberts边缘检测（用自定义卷积核）
    kernel_roberts_x = np.array([[1, 0], [0, -1]], dtype=np.float32)
    kernel_roberts_y = np.array([[0, 1], [-1, 0]], dtype=np.float32)
    roberts_x = cv2.filter2D(gray, cv2.CV_64F, kernel_roberts_x)
    roberts_y = cv2.filter2D(gray, cv2.CV_64F, kernel_roberts_y)
    roberts = cv2.magnitude(roberts_x, roberts_y)
    roberts = np.uint8(np.clip(roberts, 0, 255))
    results['roberts'] = roberts
    if save_dir:
        save_result(roberts, save_dir, "roberts.png")

    # 4. Canny边缘检测
    canny = cv2.Canny(gray, 50, 150)
    results['canny'] = canny
    if save_dir:
        save_result(canny, save_dir, "canny.png")

    # 对比展示
    if save_dir:
        show_comparison(
            [sobel, prewitt, roberts, canny],
            ["Sobel", "Prewitt", "Roberts", "Canny"],
            save_path=os.path.join(save_dir, "edge_comparison.png")
        )

    return results


# ============================================================
# 第三阶段：图像分割
# ============================================================

def segmentation(gray, save_dir=None):
    """图像分割：固定阈值 + Otsu + 连通域分析"""
    results = {}

    # 1. 固定阈值分割
    _, binary_fixed = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
    results['binary_fixed'] = binary_fixed
    if save_dir:
        save_result(binary_fixed, save_dir, "threshold_fixed.png")

    # 2. Otsu自适应阈值分割
    _, binary_otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    results['binary_otsu'] = binary_otsu
    if save_dir:
        save_result(binary_otsu, save_dir, "threshold_otsu.png")

    # 3. 连通域分析
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(binary_otsu)
    # 过滤掉太小的连通域（面积小于100的视为噪声）
    filtered = np.zeros_like(binary_otsu)
    for i in range(1, num_labels):
        if stats[i, cv2.CC_STAT_AREA] > 100:
            filtered[labels == i] = 255
    results['connected_components'] = filtered
    if save_dir:
        save_result(filtered, save_dir, "connected_components.png")

    # 对比展示
    if save_dir:
        show_comparison(
            [binary_fixed, binary_otsu, filtered],
            ["Fixed Threshold", "Otsu", "Connected Components"],
            save_path=os.path.join(save_dir, "segmentation_comparison.png")
        )

    return results


# ============================================================
# 第四阶段：形态学处理
# ============================================================

def morphology(binary, save_dir=None):
    """形态学处理：腐蚀、膨胀、开运算、闭运算"""
    results = {}
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))

    # 1. 腐蚀
    eroded = cv2.erode(binary, kernel, iterations=1)
    results['eroded'] = eroded
    if save_dir:
        save_result(eroded, save_dir, "eroded.png")

    # 2. 膨胀
    dilated = cv2.dilate(binary, kernel, iterations=2)
    results['dilated'] = dilated
    if save_dir:
        save_result(dilated, save_dir, "dilated.png")

    # 3. 开运算（先腐蚀后膨胀，去噪）
    opened = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    results['opened'] = opened
    if save_dir:
        save_result(opened, save_dir, "opened.png")

    # 4. 闭运算（先膨胀后腐蚀，填充孔洞）
    closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    results['closed'] = closed
    if save_dir:
        save_result(closed, save_dir, "closed.png")

    # 对比展示
    if save_dir:
        show_comparison(
            [binary, eroded, dilated, opened, closed],
            ["Original Binary", "Erode", "Dilate", "Open", "Close"],
            save_path=os.path.join(save_dir, "morphology_comparison.png")
        )

    return results


# ============================================================
# 第五阶段：车位状态判断
# ============================================================

def detect_parking_occupancy(image, parking_spots, method='variance'):
    """
    检测每个车位的占用状态

    参数:
        image: 输入图像
        parking_spots: list of (x, y, w, h) 车位矩形区域
        method: 检测方法 ('variance', 'edge_density', 'mean_intensity')

    返回:
        statuses: list of bool, True=占用, False=空闲
    """
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    statuses = []
    for (x, y, w, h) in parking_spots:
        roi = gray[y:y+h, x:x+w]

        if method == 'variance':
            # 灰度方差法：空车位方差小，占用车位方差大
            variance = np.var(roi)
            # 阈值可根据实际图像调整
            is_occupied = variance > 500

        elif method == 'edge_density':
            # 边缘密度法：边缘多 = 有车
            edges = cv2.Canny(roi, 50, 150)
            edge_ratio = np.sum(edges > 0) / (w * h)
            is_occupied = edge_ratio > 0.05

        elif method == 'mean_intensity':
            # 均值法：车位区域平均灰度值
            mean_val = np.mean(roi)
            is_occupied = mean_val < 100

        else:
            is_occupied = False

        statuses.append(is_occupied)

    return statuses


def detect_by_background_subtraction(current_img, background_img, parking_spots, threshold=30):
    """
    背景差分法检测车位占用

    参数:
        current_img: 当前图像
        background_img: 背景图像（空车位状态）
        parking_spots: 车位矩形区域列表
        threshold: 差分阈值
    """
    if len(current_img.shape) == 3:
        gray_curr = cv2.cvtColor(current_img, cv2.COLOR_BGR2GRAY)
    else:
        gray_curr = current_img.copy()

    if len(background_img.shape) == 3:
        gray_bg = cv2.cvtColor(background_img, cv2.COLOR_BGR2GRAY)
    else:
        gray_bg = background_img.copy()

    # 确保尺寸一致
    if gray_curr.shape != gray_bg.shape:
        gray_bg = cv2.resize(gray_bg, (gray_curr.shape[1], gray_curr.shape[0]))

    # 计算差分
    diff = cv2.absdiff(gray_curr, gray_bg)

    statuses = []
    for (x, y, w, h) in parking_spots:
        roi_diff = diff[y:y+h, x:x+w]
        # 差异超过阈值的像素占比
        changed_ratio = np.sum(roi_diff > threshold) / (w * h)
        is_occupied = changed_ratio > 0.1
        statuses.append(is_occupied)

    return statuses


# ============================================================
# 主检测流程
# ============================================================

def run_parking_detection(image_path, parking_spots, save_dir=None):
    """
    运行完整的车位检测流程

    参数:
        image_path: 图像路径
        parking_spots: 车位矩形区域列表 [(x,y,w,h), ...]
        save_dir: 结果保存目录
    """
    # 读取图像
    image = cv2.imread(image_path)
    if image is None:
        print(f"Failed to read image: {image_path}")
        return None

    # 1. 预处理
    prep_dir = os.path.join(save_dir, "preprocessing") if save_dir else None
    prep_results = preprocessing(image, prep_dir)

    # 2. 边缘检测
    edge_dir = os.path.join(save_dir, "edge_detection") if save_dir else None
    edge_results = edge_detection(prep_results['gaussian_blur'], edge_dir)

    # 3. 图像分割
    seg_dir = os.path.join(save_dir, "segmentation") if save_dir else None
    seg_results = segmentation(prep_results['gaussian_blur'], seg_dir)

    # 4. 形态学处理
    morph_dir = os.path.join(save_dir, "morphology") if save_dir else None
    morph_results = morphology(seg_results['binary_otsu'], morph_dir)

    # 5. 车位状态判断（使用方差法）
    statuses = detect_parking_occupancy(image, parking_spots, method='variance')

    # 6. 标注结果
    result_img = mark_parking_spots(image, parking_spots, statuses)
    if save_dir:
        save_result(result_img, save_dir, "final/parking_result.png")

    return result_img, statuses
