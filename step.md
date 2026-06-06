# 停车位占用检测与车牌区域增强系统设计与实现

## 项目目标

针对停车场图像/视频帧，完成两个核心任务：
1. **停车位占用检测** — 判断每个车位是否被占用，用标记框或颜色输出
2. **车牌区域增强** — 提取并增强车牌区域，使视觉上更清晰（不要求字符识别，识别可作为加分项）

---

## 必须使用的技术（评分硬性要求）

> 必须同时使用以下全部类别的技术，且达到指定数量：

| 类别 | 要求 | 可选方法 |
|------|------|----------|
| 图像预处理 | **≥2种** | 灰度化、直方图均衡化/对比度增强、均值滤波、中值滤波、高斯滤波 |
| 边缘检测 | **≥2种并对比** | Sobel、Prewitt、Roberts、Canny |
| 图像分割/目标提取 | **≥2种并对比** | 固定阈值分割、Otsu阈值分割、区域筛选、连通域分析 |
| 形态学处理 | **≥2种** | 腐蚀、膨胀、开运算、闭运算 |
| 频域处理 | **≥2种并对比** | 理想低通、巴特沃斯低通、高斯低通、高频增强、同态滤波 |
| 结果可视化 | **必须展示中间过程** | 原始图、预处理、边缘检测、二值化、形态学、频域处理、最终结果 |


## 制作流程（5阶段，共约4周）

### 第一阶段：环境搭建与数据准备

#### 步骤1：安装 Python 环境
```bash
pip install opencv-python numpy matplotlib pillow scikit-image scipy
```

#### 步骤2：准备测试数据
- **停车场俯视/侧视图像**（用于车位检测）
- **含车牌的车辆图像**（用于车牌增强）
- 可自行拍摄或使用公开数据集
- 报告中需说明数据来源、规模和特点

---

### 第二阶段：图像预处理模块

#### 步骤3：灰度化
```python
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
```

#### 步骤4：直方图均衡化 / 对比度增强（第2种预处理）
```python
# 方法1：普通直方图均衡化
equalized = cv2.equalizeHist(gray)

# 方法2：CLAHE自适应均衡化（效果更好）
clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
enhanced = clahe.apply(gray)
```

#### 步骤5：滤波去噪（第3种预处理，选做）
```python
# 均值滤波
mean_blur = cv2.blur(gray, (5,5))
# 中值滤波
median_blur = cv2.medianBlur(gray, 5)
# 高斯滤波
gaussian_blur = cv2.GaussianBlur(gray, (5,5), 0)
```

**中间结果展示**：保存并展示每种预处理的效果对比图

---

### 第三阶段：边缘检测模块

#### 步骤6：实现并对比 ≥2种边缘检测方法
```python
# Sobel
sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
sobel = cv2.magnitude(sobel_x, sobel_y)

# Canny
canny = cv2.Canny(gray, 50, 150)
```

**中间结果展示**：对比展示不同边缘检测方法的结果

---

### 第四阶段：车位占用检测核心模块

#### 步骤7：车位区域划分
- 手动标定每个车位的矩形ROI区域
- 或用线条检测（Hough变换）自动划分

#### 步骤8：图像分割 — 提取车辆区域（≥2种方法对比）
```python
# 方法1：固定阈值分割
_, binary_fixed = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)

# 方法2：Otsu自适应阈值
_, binary_otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
```

#### 步骤9：形态学处理（≥2种操作）
```python
kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5,5))
# 膨胀
dilated = cv2.dilate(binary, kernel, iterations=2)
# 闭运算（填充孔洞）
closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
```

#### 步骤10：车位状态判断
核心方法（推荐背景差分法）：
- 先获取空车位的背景图
- 新图像与背景做差分
- 差异大的区域 → 有车

备选方法：
- 灰度方差法：空车位方差小，占用车位方差大
- 边缘密度法：边缘像素占比高 → 有车

#### 步骤11：标注结果可视化
- 绿色框 = 空位，红色框 = 占位
- 显示统计（总数、已占用、空闲）

---

### 第五阶段：车牌区域增强模块

#### 步骤12：车牌定位
```python
# HSV颜色空间检测蓝色车牌
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
lower_blue = np.array([100, 50, 50])
upper_blue = np.array([130, 255, 255])
mask = cv2.inRange(hsv, lower_blue, upper_blue)
```
- 形态学闭运算连接字符
- 轮廓检测，按长宽比筛选车牌矩形

#### 步骤13：频域处理（≥2种方法并对比）
```python
# 理想低通滤波
# 巴特沃斯低通滤波
# 高斯低通滤波
# 高频增强滤波（锐化效果）
```
**必须说明每种频域方法在本项目中的用途**

#### 步骤14：车牌增强
```python
# CLAHE对比度增强
clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
enhanced_plate = clahe.apply(plate_gray)

# 锐化（Unsharp Masking）
sharpened = cv2.addWeighted(plate, 1.5, cv2.GaussianBlur(plate, (0,0), 3), -0.5, 0)
```

#### 步骤15：结果对比展示
- 原始车牌 vs 增强后车牌并排显示
- 计算 PSNR 等质量指标

---

### 第六阶段：系统整合与报告

#### 步骤16：整合所有模块
```
用户输入图像/视频
  → 预处理 → 边缘检测 → 车位检测 → 标注输出
              → 车牌定位 → 频域增强 → 增强输出
```

#### 步骤17：测试与收集失败样例
- **至少收集3个失败或效果不理想的样例**
- 分析失败原因（光照、角度、遮挡等）


## 文件结构

```
项目文件夹/
├── main.py              # 主程序入口
├── parking_detector.py  # 车位检测模块
├── plate_enhancer.py    # 车牌增强模块
├── freq_filter.py       # 频域处理模块
├── utils.py             # 工具函数
├── test_images/         # 测试图片
│   ├── parking/
│   └── plates/
├── results/             # 输出结果
│   ├── preprocessing/   # 预处理中间结果
│   ├── edge_detection/  # 边缘检测结果
│   ├── segmentation/    # 分割结果
│   ├── morphology/      # 形态学结果
│   ├── frequency/       # 频域处理结果
│   └── final/           # 最终结果
└── report/              # 报告相关
```

