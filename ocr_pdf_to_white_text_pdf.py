import os
import sys
import pymupdf as fitz  # PyMuPDF
import numpy as np
from collections import Counter, defaultdict
from typing import Dict, List, Tuple

class AdvancedPDFCleaner:
    def __init__(self):
        # 标准字体大小映射（常见中文字体大小）
        self.standard_sizes = [
            8.0, 9.0, 10.0, 10.5, 11.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0, 24.0, 26.0, 28.0, 36.0, 48.0, 72.0
        ]
        
        # 页面统计信息缓存
        self.page_stats = {}
        # 字体缓存
        self._font_cache = {}

    def get_font(self, name: str) -> "fitz.Font":
        """获取（并缓存）字体对象"""
        font = self._font_cache.get(name)
        if font is None:
            font = fitz.Font(fontname=name)
            self._font_cache[name] = font
        return font
    
    def calculate_font_size_intelligent(self, spans: List[Dict], line_bbox: Tuple[float, float, float, float]) -> float:
        """
        智能计算字体大小，使用多策略融合
        """
        # 策略1: 从span直接获取字体大小
        direct_sizes = []
        for span in spans:
            size = span.get("size", 0)
            if 5 <= size <= 72:  # 合理范围
                direct_sizes.append(size)
        
        # 策略2: 从字符bbox高度计算
        char_heights = []
        for span in spans:
            chars = span.get("chars", [])
            for char in chars:
                bbox = char.get("bbox", [0, 0, 0, 0])
                height = bbox[3] - bbox[1]
                if 2 <= height <= 50:  # 合理字符高度范围
                    char_heights.append(height)
        
        # 策略3: 从行bbox高度推断
        line_height = line_bbox[3] - line_bbox[1]
        
        # 收集所有候选尺寸
        candidates = []
        
        # 1. 直接尺寸
        if direct_sizes:
            # 使用出现频率最高的尺寸
            size_counter = Counter(direct_sizes)
            most_common = size_counter.most_common(1)
            if most_common:
                candidates.append(most_common[0][0])
        
        # 2. 字符高度
        if char_heights:
            # 使用字符高度的中位数（排除异常值）
            char_heights = np.array(char_heights)
            q25, q75 = np.percentile(char_heights, [25, 75])
            iqr = q75 - q25
            lower_bound = q25 - 1.5 * iqr
            upper_bound = q75 + 1.5 * iqr
            
            filtered_heights = [h for h in char_heights if lower_bound <= h <= upper_bound]
            if filtered_heights:
                candidates.append(np.median(filtered_heights))
        
        # 3. 行高推断（通常字体大小约为行高的0.6-0.8倍）
        if 6 <= line_height <= 50:
            candidates.append(line_height * 0.7)
        
        # 如果没有任何候选，使用默认值
        if not candidates:
            return 10.5
        
        # 从候选尺寸中选择最接近标准尺寸的一个
        best_size = candidates[0]
        
        # 如果有多个候选，使用加权平均
        if len(candidates) > 1:
            # 权重：直接尺寸 > 字符高度 > 行高推断
            weights = [0.6, 0.3, 0.1]
            weighted_sum = 0
            total_weight = 0
            for i, size in enumerate(candidates[:3]):  # 只取前三个
                weighted_sum += size * weights[i]
                total_weight += weights[i]
            
            if total_weight > 0:
                weighted_avg = weighted_sum / total_weight
                best_size = weighted_avg
        
        # 标准化到最接近的标准尺寸
        best_size = self.normalize_to_standard_size(best_size)
        
        return best_size
    
    def normalize_to_standard_size(self, size: float) -> float:
        """将计算出的字体大小标准化到最接近的标准尺寸"""
        if size <= 0:
            return 10.5
        
        # 查找最接近的标准尺寸
        closest = min(self.standard_sizes, key=lambda x: abs(x - size))
        
        # 如果与标准尺寸差距过大，使用计算值
        if abs(closest - size) / size > 0.3:  # 30%的差异阈值
            return size
        
        return closest
    
    def detect_outlier_fonts(self, page_dict: Dict, page_no: int) -> Dict:
        """检测页面中的异常字体大小"""
        font_sizes = []
        
        for block in page_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    size = span.get("size", 0)
                    if 5 <= size <= 72:
                        font_sizes.append(size)
        
        if not font_sizes:
            return {"has_outliers": False, "median_size": 10.5, "outlier_threshold": 30}
        
        # 计算统计信息
        sizes = np.array(font_sizes)
        median_size = np.median(sizes)
        
        # 计算异常值阈值（使用IQR方法）
        q25, q75 = np.percentile(sizes, [25, 75])
        iqr = q75 - q25
        lower_bound = q25 - 1.5 * iqr
        upper_bound = q75 + 1.5 * iqr
        
        # 存储页面统计信息
        self.page_stats[page_no] = {
            "median_size": median_size,
            "q25": q25,
            "q75": q75,
            "iqr": iqr,
            "lower_bound": lower_bound,
            "upper_bound": upper_bound,
            "size_distribution": Counter(font_sizes)
        }
        
        return {
            "has_outliers": any(s < lower_bound or s > upper_bound for s in sizes),
            "median_size": median_size,
            "outlier_threshold": upper_bound
        }
    
    def adjust_font_size_with_context(self, size: float, page_no: int, 
                                     spans: List[Dict], line_bbox: Tuple) -> float:
        """根据上下文调整字体大小"""
        if page_no not in self.page_stats:
            return size
        
        stats = self.page_stats[page_no]
        median_size = stats["median_size"]
        upper_bound = stats["upper_bound"]
        
        # 如果字体大小超过上限，进行调整
        if size > upper_bound:
            # 检查是否可能是标题
            line_height = line_bbox[3] - line_bbox[1]
            
            # 如果文本长度很短，可能是标题
            total_text = "".join(span.get("text", "") for span in spans)
            if len(total_text.strip()) <= 20:
                # 可能是标题，但也不能太大
                max_title_size = min(median_size * 2.5, 36)  # 最大为36pt或中位数的2.5倍
                return min(size, max_title_size)
            else:
                # 普通文本不应该太大
                return min(size, median_size * 1.5)
        
        # 如果字体大小太小，也进行调整
        lower_bound = stats["lower_bound"]
        if size < lower_bound and size > 0:
            return max(size, median_size * 0.7)  # 至少为中位数的70%
        
        return size
    
    def process_line_with_fallback(self, line: Dict, page_no: int, 
                                  page_width: float) -> List[Dict]:
        """处理一行文本，提供字体大小回退机制"""
        results = []
        spans = line.get("spans", [])
        
        if not spans:
            return results
        
        # 合并连续相同样式的span
        merged_spans = self.merge_similar_spans(spans)
        
        for span in merged_spans:
            # rawdict 模式下 span 没有 "text" 键，需要从 chars 拼接
            text = span.get("text") or "".join(
                ch.get("c", "") for ch in span.get("chars", [])
            )
            text = text.strip()
            if not text:
                continue
            
            # 获取原始字体大小
            original_size = span.get("size", 0)
            line_bbox = line.get("bbox", [0, 0, 0, 0])
            
            # 智能计算字体大小
            calculated_size = self.calculate_font_size_intelligent([span], line_bbox)
            
            # 如果计算结果与原始值差距太大，使用保守估计
            if original_size > 0:
                size_diff = abs(calculated_size - original_size) / original_size
                if size_diff > 0.5:  # 超过50%的差异
                    # 使用更保守的方法：取两者中较小的
                    calculated_size = min(calculated_size, original_size)
            
            # 根据上下文调整
            calculated_size = self.adjust_font_size_with_context(
                calculated_size, page_no, [span], line_bbox
            )
            
            # 确保字体大小在合理范围内
            calculated_size = max(5, min(calculated_size, 48))
            
            # 检测粗体
            is_bold = self.is_bold_span(span)
            
            # 计算 x 坐标和基线位置
            span_bbox = span.get("bbox", line_bbox)
            y_base = self.calculate_baseline(span, calculated_size)
            
            results.append({
                "text": text,
                "x": span_bbox[0],
                "y": y_base,
                "size": calculated_size,
                "bold": is_bold
            })
        
        return results
    
    def merge_similar_spans(self, spans: List[Dict]) -> List[Dict]:
        """合并相同样式的连续span"""
        if not spans:
            return []
        
        merged = []
        current = spans[0].copy()
        
        for i in range(1, len(spans)):
            span = spans[i]
            
            # 检查是否与当前span样式相似
            if self.are_spans_similar(current, span):
                # 合并文本
                current["text"] = current.get("text", "") + span.get("text", "")
                # 合并字符信息（保留 origin，用于基线计算）
                current["chars"] = current.get("chars", []) + span.get("chars", [])
                # 更新bbox
                current_bbox = current.get("bbox", [0, 0, 0, 0])
                span_bbox = span.get("bbox", [0, 0, 0, 0])
                if current_bbox and span_bbox:
                    current["bbox"] = [
                        min(current_bbox[0], span_bbox[0]),
                        min(current_bbox[1], span_bbox[1]),
                        max(current_bbox[2], span_bbox[2]),
                        max(current_bbox[3], span_bbox[3])
                    ]
            else:
                merged.append(current)
                current = span.copy()
        
        merged.append(current)
        return merged
    
    def are_spans_similar(self, span1: Dict, span2: Dict) -> bool:
        """判断两个span的样式是否相似"""
        # 字体大小相似性（相差不超过20%）
        size1 = span1.get("size", 0)
        size2 = span2.get("size", 0)
        if size1 > 0 and size2 > 0:
            size_diff = abs(size1 - size2) / min(size1, size2)
            if size_diff > 0.2:
                return False
        
        # 检查字体名称
        font1 = span1.get("font", "").lower()
        font2 = span2.get("font", "").lower()
        
        # 简单字体分类
        def get_font_type(font_name):
            if "bold" in font_name or "black" in font_name:
                return "bold"
            elif "italic" in font_name or "oblique" in font_name:
                return "italic"
            else:
                return "regular"
        
        if get_font_type(font1) != get_font_type(font2):
            return False
        
        return True
    
    def is_bold_span(self, span: Dict) -> bool:
        """检测span是否为粗体"""
        font = span.get("font", "").lower()
        flags = span.get("flags", 0)
        
        # 检查字体名称中的粗体标识
        if "bold" in font or "black" in font or "heavy" in font:
            return True
        
        # 检查字体标志位（位4通常表示粗体）
        if flags & (1 << 4):
            return True
        
        # 通过字体权重判断（如果有）
        weight = span.get("weight", 400)
        if weight >= 600:
            return True
        
        return False
    
    def calculate_baseline(self, span: Dict, font_size: float) -> float:
        """计算文本基线位置：优先使用字符 origin（真实基线），否则用经验公式"""
        chars = span.get("chars") or []
        origins = [
            c.get("origin")
            for c in chars
            if isinstance(c.get("origin"), (list, tuple)) and len(c.get("origin")) == 2
        ]
        if origins:
            # 取所有字符原点 y 的中位数作为行基线，排除异常值
            ys = sorted(origin[1] for origin in origins)
            return ys[len(ys) // 2]
        bbox = span.get("bbox", [0, 0, 0, 0])
        # 通常基线在bbox底部上方约字体大小的1/4处
        return bbox[3] - (font_size * 0.25)

    def choose_font(self, text: str, is_bold: bool) -> str:
        """选择字体：纯拉丁文本用 Helvetica（可保留粗体），
        含中文等字符时用 PyMuPDF 内置 CJK 字体（Helvetica 无法编码会丢字）"""
        try:
            text.encode("latin-1")
        except UnicodeEncodeError:
            return "china-s"
        return "Helvetica-Bold" if is_bold else "Helvetica"

    def fit_text_width(self, result: Dict, page_width: float) -> None:
        """文本超出页面右边界时按比例缩小字号，防止 PyMuPDF 静默截断丢字"""
        available = page_width - result["x"]
        if available <= 0:
            return
        try:
            font = self.get_font(self.choose_font(result["text"], result["bold"]))
            text_width = font.text_length(result["text"], fontsize=result["size"])
            if text_width > available:
                result["size"] = max(5.0, result["size"] * available / text_width)
        except Exception:
            pass  # 字体测量失败时保持原样
    
    def ocr_pdf_to_clean_pdf(self, input_pdf: str, output_pdf: str):
        """主处理函数"""
        if os.path.abspath(input_pdf) == os.path.abspath(output_pdf):
            print("错误: 输入和输出不能是同一个文件")
            sys.exit(1)

        doc = fitz.open(input_pdf)
        new_doc = fitz.open()
        
        print("分析PDF文档...")
        
        # 第一遍：收集统计信息
        for page_no, page in enumerate(doc, start=1):
            page_dict = page.get_text("rawdict")
            self.detect_outlier_fonts(page_dict, page_no)
        
        # 第二遍：实际处理
        for page_no, page in enumerate(doc, start=1):
            print(f"处理第 {page_no}/{len(doc)} 页...")
            
            # 创建新页面
            page_rect = page.rect
            new_page = new_doc.new_page(width=page_rect.width, height=page_rect.height)
            
            # 获取页面结构
            page_dict = page.get_text("rawdict")
            
            # 按y坐标分组行（近似处理）
            lines_by_y = defaultdict(list)
            
            for block in page_dict.get("blocks", []):
                if block.get("type") != 0:
                    continue
                
                for line in block.get("lines", []):
                    y_pos = line.get("bbox", [0, 0, 0, 0])[1]
                    y_key = round(y_pos)  # 四舍五入分组
                    lines_by_y[y_key].append(line)
            
            # 按y坐标处理（用 TextWriter，避免 insert_text 对 CJK 字体度量错误导致截断）
            writer = fitz.TextWriter(page_rect)
            for y_key in sorted(lines_by_y.keys()):
                lines = lines_by_y[y_key]
                
                # 按x坐标排序（处理多列）
                lines.sort(key=lambda l: l.get("bbox", [0, 0, 0, 0])[0])
                
                for line in lines:
                    # 处理行中的每个span
                    span_results = self.process_line_with_fallback(
                        line, page_no, page_rect.width
                    )
                    
                    for result in span_results:
                        # 选择字体：中文等字符使用内置 CJK 字体，避免 Helvetica 无法编码
                        font_name = self.choose_font(result["text"], result["bold"])

                        # 防止文本超出页面右边界被静默截断：超宽时缩小字号
                        self.fit_text_width(result, page_rect.width)
                        
                        # 插入文本
                        try:
                            writer.append(
                                (result["x"], result["y"]),
                                result["text"],
                                font=self.get_font(font_name),
                                fontsize=result["size"]
                            )
                        except Exception as e:
                            print(f"警告: 插入文本失败 - {e}")
                            # 回退到内置 CJK 字体重试
                            try:
                                writer.append(
                                    (result["x"], result["y"]),
                                    result["text"],
                                    font=self.get_font("china-s"),
                                    fontsize=10.5
                                )
                            except Exception as e2:
                                print(f"错误: 文本无法插入，已跳过（{result['text'][:20]!r}）: {e2}")
            writer.write_text(new_page, color=(0, 0, 0))
        
        # 保存结果
        new_doc.save(output_pdf, garbage=3, deflate=True)
        new_doc.close()
        doc.close()
        
        print(f"✓ 完成！输出保存至: {output_pdf}")
        
        # 打印统计信息
        print("\n字体大小统计:")
        for page_no, stats in self.page_stats.items():
            print(f"  第{page_no}页: 中位数={stats['median_size']:.1f}pt, "
                  f"范围=[{stats['q25']:.1f}-{stats['q75']:.1f}]pt")


def main():
    if len(sys.argv) != 3:
        print("用法: python ocr_pdf_to_white_text_pdf.py 输入.pdf 输出.pdf")
        sys.exit(1)
    
    input_pdf = sys.argv[1]
    output_pdf = sys.argv[2]
    
    cleaner = AdvancedPDFCleaner()
    cleaner.ocr_pdf_to_clean_pdf(input_pdf, output_pdf)


if __name__ == "__main__":
    main()
