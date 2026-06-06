# 智能停车位检测与车牌增强系统

🚗 一个基于经典图像处理算法的智能停车管理系统，能够自动检测车位占用状态并识别车牌号码。

## ✨ 功能特性

### 停车位占用检测
- 支持室内、室外网格地面、夜间等多种场景
- 双重检测机制：棕色物体检测 + 纹理遮挡检测
- 准确率：**10/10 = 100%**

### 车牌区域增强与识别
- 自动定位蓝色/黄色车牌
- 多阶段增强：去噪 → CLAHE → 高频增强 → 锐化
- OCR 识别：RapidOCR（基于 PaddleOCR）
- 准确率：**3/3 = 100%**

## 📁 项目结构

```
parking-detection-system/
├── main.py                  主程序入口
├── parking_detector.py      停车检测模块
├── plate_enhancer.py        车牌定位与增强模块
├── plate_ocr.py             车牌字符识别模块
├── freq_filter.py           频域滤波模块
├── utils.py                 工具函数
├── 必要说明文件.txt          项目详细说明
├── 运行说明.txt              运行指南
├── .gitignore               Git 忽略规则
└── README.md                本文件
```

## 🛠️ 环境要求

- Python 3.9+
- Windows / macOS / Linux

## 📦 安装

### 1. 克隆仓库

```bash
git clone https://github.com/你的用户名/parking-detection-system.git
cd parking-detection-system
```

### 2. 安装依赖

```bash
pip install opencv-python numpy matplotlib rapidocr-onnxruntime
```

### 3. 准备测试图片

在项目根目录下创建 `test_images` 文件夹：

```
test_images/
├── parking/                停车场图片
│   ├── 1.jpg
│   ├── 2.jpg
│   └── ... (1-10.jpg)
└── plates/                 车牌图片
    ├── 1.jpg
    ├── 2.jpg
    └── 10.jpg
```

**注意**：
- 停车场图片支持 `.jpg`, `.png`, `.jpeg` 格式
- 文件名可以是任意名称，系统会自动识别

## 🚀 运行

```bash
python main.py
```

运行时间约 2-3 分钟（取决于图片数量和大小）。

## 📊 运行结果

运行后会在项目根目录生成 `results` 文件夹：

```
results/
├── parking/                停车检测结果
│   ├── 1/ ... 10/
│   │   ├── original.png
│   │   ├── preprocessing/
│   │   ├── edge_detection/
│   │   ├── segmentation/
│   │   ├── morphology/
│   │   ├── frequency/
│   │   └── final/
│   │       ├── parking_result.png    ← 最终结果
│   │       └── texture_mask.png
│   └── plate_results.txt
└── plates/                 车牌识别结果
    ├── 1/ ... 10/
    │   ├── plate_0/
    │   │   ├── detected_plate.png
    │   │   ├── enhancement_pipeline.png
    │   │   └── plate_recognized.png
    └── plate_results.txt
```

## 📸 结果展示

### 停车检测

| 场景 | 结果 |
|------|------|
| 室内空位 | `Status: empty` ✅ |
| 室外空位 | `Status: empty` ✅ |
| 施工材料占用 | `Status: full` ✅ |
| 白色车辆占用 | `Status: full` ✅ |
| 夜间空位 | `Status: empty` ✅ |

### 车牌识别

| 车牌 | 识别结果 |
|------|---------|
| 京K·BT355 | 京KBT355 ✅ |
| 苏B·92912 | 苏B92912 ✅ |
| 粤A·0HA88 | 粤A0HA88 ✅ |

## 🔧 核心算法

### 图像预处理
- 灰度化、直方图均衡化、CLAHE
- 高斯去噪、中值去噪

### 边缘检测
- Sobel、Prewitt、Roberts、Canny

### 图像分割
- 固定阈值、Otsu 自动阈值、连通域分析

### 形态学处理
- 腐蚀、膨胀、开运算、闭运算

### 频域滤波
- DFT 变换
- 理想/巴特沃斯/高斯低通滤波
- 高频增强滤波

### 车牌检测
- HSV 颜色空间（蓝色/黄色车牌）
- 轮廓检测 + 评分机制

### 车牌增强
- CLAHE 对比度增强
- 高频增强滤波（频域）
- Unsharp Masking（空域）

### 字符识别
- RapidOCR（PaddleOCR 模型）
- 全图识别 + 区域匹配
- 文本后处理纠错

### 停车检测
- 棕色物体检测（HSV 颜色空间）
- 纹理遮挡检测（块对比度分析）

## 📈 测试数据

### 停车场图片
- 10 张图片
- 场景：室内、室外网格地面、夜间
- 车位状态：空闲 8 张，占用 2 张

### 车牌图片
- 3 张图片
- 车牌：丰田 京K·BT355、奥迪 苏B·92912、五菱 粤A·0HA88

## 🐛 已知问题

1. **中文显示**：OpenCV 的 `putText` 不支持中文，结果图中标注使用英文
2. **matplotlib 字体警告**：不影响功能，可安装中文字体消除
3. **夜间场景**：纹理检测可能误判，已通过亮度阈值优化

## 🔮 改进方向

1. 自适应阈值：引入机器学习方法自动调参
2. 车牌倾斜校正：添加透视变换
3. 多车位同时检测：支持批量处理
4. 实时处理：优化算法性能

## 📚 参考资料

- OpenCV 官方文档：https://docs.opencv.org/
- PaddleOCR：https://github.com/PaddlePaddle/PaddleOCR
- RapidOCR：https://github.com/RapidAI/RapidOCR

## 📄 许可证

MIT License - 可自由使用和修改

## 👥 贡献

欢迎提交 Issue 和 Pull Request！

## 📧 联系方式

如有问题，请通过 GitHub Issues 联系。

---

**课程**：数字图像处理
**院校**：暨南大学
**日期**：2026年6月
