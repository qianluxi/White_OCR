下面是一份**基于你当前代码“真实能力”重写的 GitHub README**，不夸大、不画饼，完全工程导向，适合直接放到仓库根目录使用。

你可以直接复制保存为 `README.md`。

---

# OCR PDF Clean Reconstructor

> Reconstruct a **clean, translation-friendly PDF** from an OCR-generated PDF
> while **preserving layout, text positions, and logical font sizes**.

---

## ✨ Project Background

Many OCR tools (including PDFMathTranslate input PDFs) generate PDFs that:

* Contain **hidden text layers + background artifacts**
* Introduce **black blocks / masking artifacts** after translation
* Preserve text content, but **damage layout semantics**
* Are hard to post-process reliably

This project provides a **layout-aware OCR PDF reconstruction tool** that:

* **Removes all original content**
* **Rebuilds a brand-new PDF** using only OCR text geometry
* Produces a **clean, white-background, selectable-text PDF**
* Is **highly compatible with PDFMathTranslate and similar tools**

---

## 🎯 Core Goal

> Convert an *OCR-generated PDF* into a **clean, structurally stable PDF**
> that **maintains original layout** and **avoids black block artifacts**
> in downstream translation pipelines.

---

## ✅ What This Tool Does

* Reads OCR PDFs using **PyMuPDF**
* Extracts structured text information:

  * blocks / lines / spans
  * bounding boxes
  * font sizes (when available)
* Reconstructs a **new PDF from scratch**:

  * white background
  * unified font (Helvetica / Helvetica-Bold)
  * selectable text layer
* Uses **statistical + contextual font size inference**
* Preserves:

  * line alignment
  * multi-column layouts (basic)
  * relative font hierarchy (body / title)

---

## 🚫 What This Tool Does NOT Do (By Design)

* ❌ No OCR itself
  (input must already be an OCR PDF)
* ❌ No translation
* ❌ No image extraction
* ❌ No font embedding from original PDF
* ❌ No attempt to preserve original PDF objects

This is a **clean reconstruction tool**, not a PDF editor.

---

## 🧠 Key Technical Features

### 1. Two-Pass Processing Strategy

**Pass 1 – Statistical Analysis**

* Collect font size distribution per page
* Detect outliers using IQR
* Establish page-level typographic context

**Pass 2 – Layout Reconstruction**

* Rebuild each page from text geometry
* Insert text using normalized font sizes
* Adjust baselines for visual stability

---

### 2. Intelligent Font Size Inference

Font size is determined using **multiple strategies**:

1. Direct OCR span font size (if reliable)
2. Character bounding box height
3. Line bounding box height × empirical ratio
4. Contextual correction using page statistics

Fallback behavior:

* If font size is unreliable → use **10.5 pt (小五号)**

---

### 3. Robust Noise Handling

* Merges visually similar spans
* Filters extreme font outliers
* Prevents oversized text from breaking layout
* Prevents undersized text from disappearing

---

## 📂 Project Structure

```text
.
├── ocr_pdf_to_white_text_pdf.py   # Main script (can replace legacy version)
├── README.md
└── requirements.txt
```

---

## 🧪 Usage

### 1. Install Dependencies

```bash
pip install pymupdf numpy
```

> Python ≥ 3.8 recommended

---

### 2. Run the Script

```bash
python ocr_pdf_to_white_text_pdf.py input_ocr.pdf output_clean.pdf
```

* `input_ocr.pdf`
  An OCR-generated PDF with a text layer

* `output_clean.pdf`
  A clean, reconstructed, translation-friendly PDF

---

## 🔁 Drop-in Replacement

This script is designed to be a **drop-in replacement** for legacy tools such as:

```text
ocr_pdf_to_white_text_pdf.py
```

* Same input/output semantics
* Same CLI interface
* Improved layout stability
* Eliminates black block artifacts

You can safely replace the old script with this one.

---

## 📌 Typical Workflow

```text
Original PDF
    ↓
OCR Tool (ABBYY / PaddleOCR / DeepSeek OCR / etc.)
    ↓
OCR PDF
    ↓
[This Tool]
    ↓
Clean PDF (white background, selectable text)
    ↓
PDFMathTranslate / Translation Pipeline
```

---

## 🧩 Compatibility

Tested and suitable for:

* PDFMathTranslate
* Math / academic PDFs
* Engineering documentation
* Mixed Chinese / English OCR PDFs

---

## ⚠️ Known Limitations

* Font family is unified (Helvetica)
* Exact kerning is not preserved
* Complex tables may degrade
* Multi-column detection is heuristic-based

These are **intentional trade-offs** to ensure stability and translation compatibility.

---

## 📜 License

MIT License
Free to use, modify, and integrate into larger pipelines.

---

## 🤝 Contributing

Contributions are welcome, especially in:

* Multi-column detection
* Baseline refinement
* Line spacing normalization
* Translation-aware layout hints

---

## 📣 Final Note

This project focuses on **engineering robustness**, not visual perfection.

If your goal is:

* *“No black blocks”*
* *“Stable translation input”*
* *“Recover usable PDFs from OCR output”*

then this tool is designed exactly for that purpose.

---

