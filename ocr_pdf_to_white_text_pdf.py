import sys
import pikepdf
from pikepdf import Name


def remove_all_images_and_xobjects(page):
    """
    彻底移除页面中的所有 Image / XObject 引用
    """
    if "/Resources" not in page:
        return

    resources = page["/Resources"]

    # 1. 删除 XObject（Image / Form 等）
    if "/XObject" in resources:
        xobjects = resources["/XObject"]
        for name in list(xobjects.keys()):
            del xobjects[name]

    # 2. 删除 Pattern（有时会间接引用图像）
    if "/Pattern" in resources:
        del resources["/Pattern"]

    # 3. 删除 Shading（防止残留背景渲染）
    if "/Shading" in resources:
        del resources["/Shading"]


def strip_image_drawing_ops(page, pdf):
    """
    从内容流中移除所有图像绘制指令（Do）
    只保留文本 / 路径指令
    """
    if "/Contents" not in page:
        return

    contents = page.Contents

    if isinstance(contents, pikepdf.Array):
        streams = contents
    else:
        streams = [contents]

    new_streams = []

    for stream in streams:
        data = stream.read_bytes()

        lines = data.split(b"\n")
        cleaned = []

        for line in lines:
            stripped = line.strip()

            # 删除所有 XObject 绘制指令： /Im0 Do
            if stripped.endswith(b" Do"):
                continue

            cleaned.append(line)

        new_data = b"\n".join(cleaned)

        if new_data.strip():
            new_streams.append(pikepdf.Stream(pdf, new_data))

    if not new_streams:
        # 保证页面还有一个空内容流，防止某些工具崩溃
        new_streams = [pikepdf.Stream(pdf, b"")]

    page.Contents = pikepdf.Array(new_streams)


def process_pdf(input_pdf, output_pdf):
    with pikepdf.open(input_pdf, allow_overwriting_input=True) as pdf:
        for page in pdf.pages:
            strip_image_drawing_ops(page, pdf)
            remove_all_images_and_xobjects(page)

        pdf.save(output_pdf)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python ocr_pdf_to_white_text_pdf.py input.pdf output.pdf")
        sys.exit(1)

    input_pdf = sys.argv[1]
    output_pdf = sys.argv[2]

    process_pdf(input_pdf, output_pdf)
    print(f"Done. Output saved to: {output_pdf}")
