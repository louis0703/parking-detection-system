"""
工具函数模块
提供图像保存、可视化、PSNR计算等通用功能
"""

import cv2
import numpy as np
import os


def save_result(image, save_dir, filename):
    """保存处理结果图像"""
    os.makedirs(save_dir, exist_ok=True)
    path = os.path.join(save_dir, filename)
    cv2.imwrite(path, image)
    return path


def calc_psnr(img1, img2):
    """计算两幅图像的PSNR（峰值信噪比）"""
    if img1.shape != img2.shape:
        img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]))
    mse = np.mean((img1.astype(float) - img2.astype(float)) ** 2)
    if mse == 0:
        return float('inf')
    return 10 * np.log10(255.0 ** 2 / mse)


def calc_contrast(image):
    """计算图像对比度（标准差）"""
    if len(image.shape) == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return np.std(image)


def show_comparison(images, titles, save_path=None, figsize=(16, 4)):
    """并排展示多张图像进行对比"""
    import matplotlib.pyplot as plt
    n = len(images)
    fig, axes = plt.subplots(1, n, figsize=figsize)
    if n == 1:
        axes = [axes]
    for i, (img, title) in enumerate(zip(images, titles)):
        if len(img.shape) == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        axes[i].imshow(img, cmap='gray')
        axes[i].set_title(title)
        axes[i].axis('off')
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()


def mark_parking_spots(image, spots, statuses):
    """
    在图像上标注车位状态
    spots: list of (x, y, w, h) 矩形区域
    statuses: list of bool, True=占用, False=空闲
    """
    result = image.copy()
    occupied = 0
    free = 0
    for (x, y, w, h), occupied_flag in zip(spots, statuses):
        if occupied_flag:
            color = (0, 0, 255)  # 红色：占用
            label = "Occupied"
            occupied += 1
        else:
            color = (0, 255, 0)  # 绿色：空闲
            label = "Free"
            free += 1
        cv2.rectangle(result, (x, y), (x + w, y + h), color, 2)
        cv2.putText(result, label, (x, y - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
    # 显示统计
    total = len(spots)
    text = f"Total: {total} | Occupied: {occupied} | Free: {free}"
    cv2.putText(result, text, (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    return result
