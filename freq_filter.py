"""
频域处理模块
实现理想低通、巴特沃斯低通、高斯低通、高频增强等频域滤波器
"""

import cv2
import numpy as np


def dft_process(image):
    """将图像转换到频域，返回频谱"""
    if len(image.shape) == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    image = image.astype(np.float32)
    # 傅里叶变换
    dft = cv2.dft(image, flags=cv2.DFT_COMPLEX_OUTPUT)
    # 中心化：将低频移到中心
    dft_shift = np.fft.fftshift(dft, axes=[0, 1])
    # 计算幅度谱
    magnitude = cv2.magnitude(dft_shift[:, :, 0], dft_shift[:, :, 1])
    magnitude = 20 * np.log(magnitude + 1)
    return dft_shift, magnitude


def idft_process(dft_shift, original_shape):
    """从频域逆变换回空域"""
    # 逆中心化
    f_ishift = np.fft.ifftshift(dft_shift, axes=[0, 1])
    # 逆傅里叶变换
    img_back = cv2.idft(f_ishift, flags=cv2.DFT_SCALE | cv2.DFT_REAL_OUTPUT)
    # 裁剪到原始尺寸
    img_back = img_back[:original_shape[0], :original_shape[1]]
    img_back = np.clip(img_back, 0, 255).astype(np.uint8)
    return img_back


def ideal_lowpass_filter(shape, cutoff):
    """理想低通滤波器
    cutoff: 截止频率（像素距离）
    """
    rows, cols = shape[:2]
    crow, ccol = rows // 2, cols // 2
    u = np.arange(rows)
    v = np.arange(cols)
    U, V = np.meshgrid(v, u)
    D = np.sqrt((U - ccol) ** 2 + (V - crow) ** 2)
    mask = np.zeros((rows, cols), np.float32)
    mask[D <= cutoff] = 1
    return mask


def butterworth_lowpass_filter(shape, cutoff, n=2):
    """巴特沃斯低通滤波器
    cutoff: 截止频率
    n: 滤波器阶数
    """
    rows, cols = shape[:2]
    crow, ccol = rows // 2, cols // 2
    u = np.arange(rows)
    v = np.arange(cols)
    U, V = np.meshgrid(v, u)
    D = np.sqrt((U - ccol) ** 2 + (V - crow) ** 2)
    # 避免除零
    D = np.where(D == 0, 1e-6, D)
    H = 1 / (1 + (D / cutoff) ** (2 * n))
    return H


def gaussian_lowpass_filter(shape, cutoff):
    """高斯低通滤波器
    cutoff: 截止频率（标准差）
    """
    rows, cols = shape[:2]
    crow, ccol = rows // 2, cols // 2
    u = np.arange(rows)
    v = np.arange(cols)
    U, V = np.meshgrid(v, u)
    D2 = (U - ccol) ** 2 + (V - crow) ** 2
    H = np.exp(-D2 / (2 * cutoff ** 2))
    return H


def high_frequency_emphasis_filter(shape, cutoff, a=0.5, b=1.5):
    """高频增强滤波器
    H = a + b * H_hp，其中 H_hp = 1 - H_lp
    a: 高频分量增益
    b: 低频分量增益
    """
    H_lp = gaussian_lowpass_filter(shape, cutoff)
    H_hp = 1 - H_lp
    H = a + b * H_hp
    return H


def apply_freq_filter(image, filter_mask):
    """将频域滤波器应用到图像上"""
    if len(image.shape) == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    original_shape = image.shape
    dft_shift, _ = dft_process(image)

    # 扩展滤波器为双通道
    mask_3d = np.stack([filter_mask, filter_mask], axis=-1)
    # 应用滤波器
    filtered = dft_shift * mask_3d
    # 逆变换
    result = idft_process(filtered, original_shape)
    return result


def get_filter_magnitude(filter_mask):
    """获取滤波器的可视化频谱"""
    return (filter_mask * 255).astype(np.uint8)


def compare_freq_filters(image, save_dir):
    """对比不同频域滤波器的效果"""
    from utils import save_result, show_comparison

    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    rows, cols = gray.shape
    shape = gray.shape

    # 原始频谱
    _, orig_mag = dft_process(gray)

    # 各种滤波器
    cutoff = 50

    # 理想低通
    H_ideal = ideal_lowpass_filter(shape, cutoff)
    result_ideal = apply_freq_filter(gray, H_ideal)
    _, mag_ideal = dft_process(result_ideal)
    save_result(get_filter_magnitude(H_ideal), save_dir, "ideal_lpf_mask.png")
    save_result(result_ideal, save_dir, "ideal_lpf_result.png")

    # 巴特沃斯低通
    H_butter = butterworth_lowpass_filter(shape, cutoff, n=2)
    result_butter = apply_freq_filter(gray, H_butter)
    _, mag_butter = dft_process(result_butter)
    save_result(get_filter_magnitude(H_butter), save_dir, "butterworth_lpf_mask.png")
    save_result(result_butter, save_dir, "butterworth_lpf_result.png")

    # 高斯低通
    H_gauss = gaussian_lowpass_filter(shape, cutoff)
    result_gauss = apply_freq_filter(gray, H_gauss)
    _, mag_gauss = dft_process(result_gauss)
    save_result(get_filter_magnitude(H_gauss), save_dir, "gaussian_lpf_mask.png")
    save_result(result_gauss, save_dir, "gaussian_lpf_result.png")

    # 高频增强
    H_hfe = high_frequency_emphasis_filter(shape, cutoff)
    result_hfe = apply_freq_filter(gray, H_hfe)
    _, mag_hfe = dft_process(result_hfe)
    save_result(get_filter_magnitude(H_hfe), save_dir, "hfe_mask.png")
    save_result(result_hfe, save_dir, "hfe_result.png")

    # 保存原始频谱
    save_result(orig_mag.astype(np.uint8), save_dir, "original_spectrum.png")

    # 对比展示
    show_comparison(
        [result_ideal, result_butter, result_gauss, result_hfe],
        ["Ideal LPF", "Butterworth LPF", "Gaussian LPF", "High Freq Emphasis"],
        save_path=os.path.join(save_dir, "freq_comparison.png")
    )
    return result_ideal, result_butter, result_gauss, result_hfe


import os
