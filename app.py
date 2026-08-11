from flask import Flask, render_template, request, send_file, redirect, url_for, flash
import os
import secrets
import subprocess
import sys
import pikepdf

app = Flask(__name__)
# 会话密钥：优先从环境变量读取，否则随机生成
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

# 限制上传大小（默认 200MB）
app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("MAX_UPLOAD_MB", "200")) * 1024 * 1024

@app.errorhandler(413)
def too_large(_e):
    flash("文件过大，请上传 200MB 以内的 PDF")
    return redirect(url_for("index"))

# 文件夹
UPLOAD_DIR = "uploads"
OCR_DIR = "ocr_outputs"
WHITE_DIR = "white_outputs"
MERGED_DIR = "merged_outputs"

# 创建目录
for d in [UPLOAD_DIR, OCR_DIR, WHITE_DIR, MERGED_DIR]:
    os.makedirs(d, exist_ok=True)

# --- 工具函数 ---
def make_output_name(original_filename, suffix):
    """根据原始文件名生成输出文件名，去掉时间戳"""
    name, ext = os.path.splitext(original_filename)
    return f"{name}_{suffix}{ext}"

_RESERVED_WIN_NAMES = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}
_FORBIDDEN_CHARS = set('<>:"/\\|?*')

def safe_filename(filename):
    """清洗上传文件名：去除路径、控制字符和 Windows 非法字符，保留中文"""
    name = str(filename).replace("\\", "/").split("/")[-1]
    name = "".join(ch for ch in name if ch.isprintable() and ch not in _FORBIDDEN_CHARS)
    name = name.strip().rstrip(".")
    if not name:
        return "upload.pdf"
    base, _ext = os.path.splitext(name)
    if base.lower() in _RESERVED_WIN_NAMES:
        name = "file_" + name
    return name[:120]

def is_pdf_filename(filename):
    """校验文件名是否为 PDF"""
    return filename.lower().endswith(".pdf")

def _remove_files(*paths):
    """尽力删除失败时产生的文件（忽略错误）"""
    for p in paths:
        try:
            if os.path.isfile(p):
                os.remove(p)
        except OSError:
            pass

def merge_alternate_pdfs(input_pdf, white_pdf, output_pdf):
    """
    将 input_pdf 和 white_pdf 交替合并页，生成 output_pdf。
    例如：
        input_pdf: 页 1,2,3
        white_pdf: 页 a,b,c
        输出: 1,a,2,b,3,c
    """
    with pikepdf.open(input_pdf) as pdf_in, pikepdf.open(white_pdf) as pdf_white:
        merged_pdf = pikepdf.Pdf.new()
        # 获取页数
        n_in = len(pdf_in.pages)
        n_white = len(pdf_white.pages)
        max_pages = max(n_in, n_white)

        for i in range(max_pages):
            if i < n_in:
                merged_pdf.pages.append(pdf_in.pages[i])
            if i < n_white:
                merged_pdf.pages.append(pdf_white.pages[i])

        merged_pdf.save(output_pdf)

# --- 调用 OCRmyPDF Docker ---
def run_ocrmypdf_docker(
    input_pdf,
    output_pdf,
    languages="chi_sim+eng",
    rotate=True,
    deskew=True,
    jobs=4,
    force_ocr=False
):
    cmd = [
        "docker", "run", "--rm",
        "-v", f"{os.path.abspath(UPLOAD_DIR)}:/input",
        "-v", f"{os.path.abspath(OCR_DIR)}:/output",
        "jbarlow83/ocrmypdf-alpine"
        # ❌ 不要再写 "ocrmypdf"
    ]

    # ===== OCR 参数 =====
    cmd += ["-l", languages]

    if rotate:
        cmd.append("--rotate-pages")

    if deskew:
        cmd.append("--deskew")

    if jobs and isinstance(jobs, int) and jobs > 0:
        cmd += ["-j", str(jobs)]

    # ⭐ 强制 OCR
    if force_ocr:
        cmd.append("--force-ocr")

    # 输入 / 输出（必须放最后）
    cmd += [
        f"/input/{os.path.basename(input_pdf)}",
        f"/output/{os.path.basename(output_pdf)}"
    ]

    subprocess.run(cmd, check=True)
# --- 调用白底化脚本 ---
def run_white_pdf(input_pdf, output_pdf):
    subprocess.run(
        [sys.executable, "ocr_pdf_to_white_text_pdf.py", input_pdf, output_pdf],
        check=True
    )
    
# --- 首页 ---
@app.route("/")
def index():
    ocr_files = [
        f for f in os.listdir(OCR_DIR)
        if f.lower().endswith(".pdf")
    ]

    white_files = [
        f for f in os.listdir(WHITE_DIR)
        if f.lower().endswith(".pdf")
    ]

    merged_files = [
        f for f in os.listdir(MERGED_DIR)
        if f.lower().endswith(".pdf")
    ]

    return render_template(
        "index.html",
        ocr_files=ocr_files,
        white_files=white_files,
        merged_files=merged_files
    )

# --- 第一步：上传 PDF 生成 OCR PDF ---
@app.route("/upload", methods=["POST"])
def upload():
    f = request.files.get("pdf")
    if not f or f.filename == "":
        flash("请选择 PDF 文件")
        return redirect(url_for("index"))

    filename = safe_filename(f.filename)
    if not is_pdf_filename(filename):
        flash("仅支持 PDF 文件")
        return redirect(url_for("index"))

    # ===== 表单参数 =====
    languages = request.form.get("languages", "chi_sim+eng")
    rotate = request.form.get("rotate") == "on"
    deskew = request.form.get("deskew") == "on"
    force_ocr = request.form.get("force_ocr") == "on"

    # ⭐ jobs 特殊处理（关键修复点）
    jobs_raw = request.form.get("jobs", "auto")
    if jobs_raw == "auto":
        jobs = None           # 不传 --jobs
    else:
        try:
            jobs = int(jobs_raw)
        except ValueError:
            flash("并行任务数参数错误")
            return redirect(url_for("index"))

    # ===== 保存上传文件 =====
    input_pdf = os.path.join(UPLOAD_DIR, filename)
    f.save(input_pdf)

    # ===== OCR 输出文件 =====
    ocr_pdf_name = make_output_name(filename, "ocr")
    ocr_pdf_path = os.path.join(OCR_DIR, ocr_pdf_name)

    try:
        run_ocrmypdf_docker(
            input_pdf=input_pdf,
            output_pdf=ocr_pdf_path,
            languages=languages,
            rotate=rotate,
            deskew=deskew,
            jobs=jobs,              # ⭐ None 或 int
            force_ocr=force_ocr
        )
    except Exception as e:
        flash(f"OCR 失败: {e}")
        _remove_files(input_pdf, ocr_pdf_path)
        return redirect(url_for("index"))

    flash(f"OCR PDF 已生成: {ocr_pdf_name}")
    return redirect(url_for("index"))

# --- 第二步：生成白底 PDF ---
@app.route("/generate_white", methods=["POST"])
def generate_white():
    uploaded_file = request.files.get("pdf")
    if not uploaded_file or uploaded_file.filename == "":
        flash("请上传 PDF 文件")
        return redirect(url_for("index"))

    filename = safe_filename(uploaded_file.filename)
    if not is_pdf_filename(filename):
        flash("仅支持 PDF 文件")
        return redirect(url_for("index"))

    # 上传文件先放在 uploads/
    input_pdf = os.path.join(UPLOAD_DIR, filename)
    uploaded_file.save(input_pdf)

    # 白底 PDF 输出
    white_pdf_name = make_output_name(filename, "white")
    white_pdf_path = os.path.join(WHITE_DIR, white_pdf_name)

    try:
        run_white_pdf(input_pdf, white_pdf_path)
    except Exception as e:
        flash(f"白底化处理失败: {e}")
        _remove_files(input_pdf, white_pdf_path)
        return redirect(url_for("index"))

    flash(f"白底 PDF 已生成: {white_pdf_name}，可下载")
    return redirect(url_for("index"))

# --- 下载文件 ---
@app.route("/download/<folder>/<filename>")
def download(folder, filename):
    folder_map = {
        "uploads": UPLOAD_DIR,        # 原始上传 PDF
        "ocr": OCR_DIR,               # OCR 后 PDF
        "white": WHITE_DIR,           # 白底 PDF
        "merged": MERGED_DIR          # 交替合并 PDF
    }

    # 校验目录是否合法
    if folder not in folder_map:
        flash("非法下载目录")
        return redirect(url_for("index"))

    directory = os.path.abspath(folder_map[folder])
    file_path = os.path.abspath(os.path.join(directory, filename))

    # 校验文件名不能逃逸目标目录（防路径穿越）
    if not (file_path == directory or file_path.startswith(directory + os.sep)):
        flash("非法文件名")
        return redirect(url_for("index"))

    # 校验文件是否存在
    if not os.path.isfile(file_path):
        flash(f"文件不存在：{filename}")
        return redirect(url_for("index"))

    # 发送文件
    return send_file(
        file_path,
        as_attachment=True,
        download_name=filename  # Flask >=2.0，确保下载名正确
    )

@app.route("/merge_pdfs", methods=["POST"])
def merge_pdfs():
    input_file = request.files.get("input_pdf")
    white_file = request.files.get("white_pdf")

    if not input_file or not white_file:
        flash("请上传两个 PDF 文件")
        return redirect(url_for("index"))

    input_name = safe_filename(input_file.filename)
    white_name = safe_filename(white_file.filename)
    if not (is_pdf_filename(input_name) and is_pdf_filename(white_name)):
        flash("请上传两个 PDF 文件")
        return redirect(url_for("index"))

    # 保存上传文件到 uploads/
    input_path = os.path.join(UPLOAD_DIR, input_name)
    white_path = os.path.join(WHITE_DIR, white_name)
    input_file.save(input_path)
    white_file.save(white_path)

    # 输出文件
    merged_name = f"{os.path.splitext(input_name)[0]}_merged.pdf"
    merged_path = os.path.join(MERGED_DIR, merged_name)

    try:
        merge_alternate_pdfs(input_path, white_path, merged_path)
    except Exception as e:
        flash(f"合并失败: {e}")
        _remove_files(input_path, white_path, merged_path)
        return redirect(url_for("index"))

    flash(f"合并 PDF 已生成: {merged_name}")
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG", "0") == "1",
        use_reloader=False
    )
