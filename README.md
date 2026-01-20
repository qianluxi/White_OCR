下面是一份**可直接放到 GitHub 仓库根目录的 `README.md`（中文版）**，内容、结构和表述均按**工程级项目**标准撰写，适合对外发布、协作或长期维护。

---

# White OCR Web

**基于 OCRmyPDF 的 PDF OCR / 白底化 / 交替合并 Web 工具**

## 📌 项目简介

**White OCR Web** 是一个基于 **Flask + OCRmyPDF（Docker）** 的 Web 工程，用于对扫描版 PDF 进行：

1. **OCR 文字识别（增加可搜索文本层）**
2. **白底文本 PDF 生成（无 OCR 页面保留空白页）**
3. **原始 PDF 与白底 PDF 的交替合并**

本项目面向 **工程师 / 技术用户**，强调：

* 参数可控
* 行为可预测
* 文件结构清晰
* 处理流程可扩展

适用于工程文档、扫描资料、历史档案等 PDF 的结构化处理。

---

## ✨ 核心功能

### ① OCR 文字识别（OCRmyPDF）

* 使用 **Docker 容器方式调用 OCRmyPDF**
* 支持多语言 OCR（如 `chi_sim+eng`）
* 支持常见扫描问题修复：

  * 页面旋转修正
  * 去倾斜（deskew）
* 支持多核并行处理（自动或指定核心数）
* 输出标准 PDF / PDF-A

### ② 白底文本 PDF 生成

* 对 OCR 后 PDF **逐页处理**
* 有文字页 → 生成白底文本页
* 无 OCR 文本页 → **保留空白页，不跳过**
* 确保页数严格一致

### ③ PDF 交替合并

* 输入：

  * 原始 / OCR PDF
  * 白底 PDF
* 输出：

  * 按页交替拼接：
    `1, a, 2, b, 3, c ...`
* 常用于：

  * 原图 + 文本对照
  * 审核 / 标注场景

---

## 🧱 项目结构

```text
white_ocr_web/
├─ app.py                      # Flask 主程序
├─ ocr_pdf_to_white_text_pdf.py# 白底 PDF 生成逻辑
├─ templates/
│  └─ index.html               # 前端页面（工程师级参数 UI）
├─ uploads/                    # 原始上传 PDF
├─ ocr_outputs/                # OCR 后 PDF
├─ white_outputs/              # 白底 PDF
├─ merged_outputs/             # 交替合并 PDF
└─ README.md
```

---

## 🛠️ 环境依赖

### 必需组件

* **Docker**
* **Python ≥ 3.9**

### Docker 镜像

使用官方 OCRmyPDF Alpine 镜像：

```text
jbarlow83/ocrmypdf-alpine
```

首次运行时 Docker 会自动拉取。

---

## 🚀 快速启动

### 1️⃣ 安装 Python 依赖

```bash
pip install flask pypdf
```

（如你已有虚拟环境，建议在 venv 中安装）

---

### 2️⃣ 启动 Flask 服务

```bash
python app.py
```

默认访问地址：

```text
http://127.0.0.1:5000
```

---

## 🖥️ Web 使用说明

### 第一步：生成 OCR PDF

* 上传扫描版 PDF
* 设置 OCR 参数：

  * OCR 语言（如 `chi_sim+eng`）
  * 是否旋转修正
  * 是否去倾斜
  * 并行核心数（auto / 指定数值）
* 点击 **生成 OCR PDF**
* 处理过程中显示 loading 进度提示
* 输出文件保存在：

```text
ocr_outputs/
```

---

### 第二步：生成白底 PDF

* 上传 OCR 后 PDF（可来自本项目或外部）
* 逐页生成白底文本 PDF
* 输出文件保存在：

```text
white_outputs/
```

---

### 第三步：交替合并 PDF

* 上传：

  * 原始 / OCR PDF
  * 白底 PDF
* 按页交替合并
* 输出文件保存在：

```text
merged_outputs/
```

---

## ⚙️ OCR 参数说明（工程级）

| 参数     | 说明                            |
| ------ | ----------------------------- |
| OCR 语言 | Tesseract 语言包，如 `chi_sim+eng` |
| 旋转修正   | 自动修正扫描页旋转                     |
| 去倾斜    | 修正扫描仪倾斜                       |
| 并行处理   | 自动（CPU 核心数）或指定线程数             |
| 输出类型   | pdf / pdfa                    |

⚠️ 说明：

* `并行处理=auto` 会在后端转换为 CPU 核心数
* OCRmyPDF **不支持 `-j auto`，必须是整数**

---

## 🧠 设计说明

### 为什么使用 Docker 调用 OCRmyPDF？

* 避免本地环境污染
* 避免 Tesseract / Ghostscript 依赖问题
* 提高跨平台一致性
* 便于后续部署到服务器

---

### 为什么无 OCR 页面保留空白页？

这是一个**刻意的工程决策**：

* 保证输入 / 输出 PDF **页数严格一致**
* 为后续合并、索引、对照提供基础
* 避免页号错位导致的数据问题

---

## 📎 适用场景

* 工程图纸 / 扫描规范 OCR
* 历史档案数字化
* PDF 内容结构化处理
* 原图 + 文本对照审阅

---

## 📄 License

本项目仅为工程示例，OCRmyPDF 与 Tesseract 请遵循其各自开源协议。


你这个工程，已经非常值得长期维护了。
