import sys
import pikepdf
from pikepdf import Name, Stream


def make_white_background(page, pdf):
    """
    在页面最底层插入白色背景
    """
    media_box = page.MediaBox
    width = float(media_box[2])
    height = float(media_box[3])

    white_bg_ops = f"""
q
1 1 1 rg
0 0 {width} {height} re
f
Q
""".encode("ascii")

    # 读取原始内容流（可能是单个或多个）
    if isinstance(page.Contents, pikepdf.Array):
        original = b"".join(
            obj.read_bytes() for obj in page.Contents
        )
    else:
        original = page.Contents.read_bytes()

    # 新内容：白底 + 原内容
    page.Contents = Stream(pdf, white_bg_ops + original)


def remove_image_xobjects(page):
    """
    删除页面中所有 Image XObject
    """
    if "/Resources" not in page:
        return

    resources = page["/Resources"]

    if "/XObject" not in resources:
        return

    xobjects = resources["/XObject"]

    for name in list(xobjects.keys()):
        obj = xobjects[name]
        if obj.get("/Subtype") == Name("/Image"):
            del xobjects[name]


def process_pdf(input_pdf, output_pdf):
    with pikepdf.open(input_pdf) as pdf:
        for page in pdf.pages:
            # 1. 删除所有扫描图像
            remove_image_xobjects(page)

            # 2. 无论是否有 OCR 文本，都插入白色背景
            make_white_background(page, pdf)

        pdf.save(output_pdf)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python ocr_pdf_to_white_text_pdf.py input.pdf output.pdf")
        sys.exit(1)

    input_pdf = sys.argv[1]
    output_pdf = sys.argv[2]

    process_pdf(input_pdf, output_pdf)
    print(f"Done. Output saved to: {output_pdf}")
