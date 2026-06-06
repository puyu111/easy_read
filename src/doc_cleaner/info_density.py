"""信息密度评估模块。

计算文档的压缩比、术语密度、信息保留率等指标。
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class DensityReport:
    """单个文件的信息密度报告。"""
    filename: str
    original_size: int = 0           # 原始字节数
    cleaned_size: int = 0            # 清洗后字节数
    original_chars: int = 0          # 原始字符数
    cleaned_chars: int = 0           # 清洗后字符数
    compression_ratio: float = 0.0   # 压缩比 (cleaned / original)
    chinese_ratio: float = 0.0       # 中文字符占比
    term_density: float = 0.0        # 术语密度
    heading_count: int = 0           # 标题数量
    table_rows: int = 0              # 表格行数
    code_blocks: int = 0             # 代码块数
    formula_count: int = 0           # 公式数量
    standard_refs: int = 0           # 标准引用数量
    noise_removed: int = 0           # 去除的噪声数量
    info_retention: float = 0.0      # 信息保留率估算


@dataclass
class BatchDensityReport:
    """批量处理的密度报告汇总。"""
    total_files: int = 0
    total_original_bytes: int = 0
    total_cleaned_bytes: int = 0
    avg_compression_ratio: float = 0.0
    avg_term_density: float = 0.0
    avg_info_retention: float = 0.0
    total_noise_removed: int = 0
    files: list = field(default_factory=list)


def _load_glossary(glossary_path: Optional[str]) -> set[str]:
    """加载术语词典。"""
    terms = set()
    if glossary_path and Path(glossary_path).exists():
        with open(glossary_path, "r", encoding="utf-8") as f:
            for line in f:
                term = line.strip()
                if term and not term.startswith("#"):
                    terms.add(term)
    return terms


def _count_chinese(text: str) -> int:
    """统计中文字符数。"""
    return sum(1 for c in text if '\u4e00' <= c <= '\u9fff')


def _count_headings(text: str) -> int:
    """统计 Markdown 标题数。"""
    return len(re.findall(r'^#{1,6}\s+', text, re.MULTILINE))


def _count_table_rows(text: str) -> int:
    """统计表格行数。"""
    return len(re.findall(r'^\|.*\|$', text, re.MULTILINE))


def _count_code_blocks(text: str) -> int:
    """统计代码块数。"""
    return len(re.findall(r'^```', text, re.MULTILINE)) // 2


def _count_formulas(text: str) -> int:
    """统计公式数量。"""
    display = len(re.findall(r'\$\$.*?\$\$', text, re.DOTALL))
    inline = len(re.findall(r'(?<!\$)\$(?!\$).+?(?<!\$)\$(?!\$)', text))
    return display + inline


def _count_standard_refs(text: str) -> int:
    """统计标准引用数量。"""
    patterns = [
        r'GB[/\-T]\s*\d+',
        r'ISO\s*\d+',
        r'IEC\s*\d+',
        r'IEEE\s*\d+',
    ]
    total = 0
    for p in patterns:
        total += len(re.findall(p, text, re.IGNORECASE))
    return total


def _count_terms(text: str, glossary: set[str]) -> int:
    """统计术语出现次数。"""
    if not glossary:
        return 0
    count = 0
    for term in glossary:
        count += len(re.findall(re.escape(term), text))
    return count


def evaluate_density(
    original_text: str,
    cleaned_text: str,
    filename: str = "",
    glossary_path: Optional[str] = None,
) -> DensityReport:
    """评估单个文件的信息密度。

    Args:
        original_text: 原始文本。
        cleaned_text: 清洗后的文本。
        filename: 文件名。
        glossary_path: 术语词典路径。

    Returns:
        DensityReport 信息密度报告。
    """
    glossary = _load_glossary(glossary_path)

    original_chars = len(original_text)
    cleaned_chars = len(cleaned_text)

    report = DensityReport(filename=filename)
    report.original_size = len(original_text.encode("utf-8"))
    report.cleaned_size = len(cleaned_text.encode("utf-8"))
    report.original_chars = original_chars
    report.cleaned_chars = cleaned_chars
    report.compression_ratio = round(cleaned_chars / original_chars, 4) if original_chars > 0 else 0.0

    chinese = _count_chinese(cleaned_text)
    report.chinese_ratio = round(chinese / cleaned_chars, 4) if cleaned_chars > 0 else 0.0

    term_count = _count_terms(cleaned_text, glossary)
    total_words = len(cleaned_text.split())
    report.term_density = round(term_count / total_words, 4) if total_words > 0 else 0.0

    report.heading_count = _count_headings(cleaned_text)
    report.table_rows = _count_table_rows(cleaned_text)
    report.code_blocks = _count_code_blocks(cleaned_text)
    report.formula_count = _count_formulas(cleaned_text)
    report.standard_refs = _count_standard_refs(cleaned_text)

    # 信息保留率：基于关键元素的保留比例
    key_elements_original = (
        _count_headings(original_text)
        + _count_table_rows(original_text)
        + _count_code_blocks(original_text)
        + _count_formulas(original_text)
        + _count_standard_refs(original_text)
    )
    key_elements_cleaned = (
        report.heading_count
        + report.table_rows
        + report.code_blocks
        + report.formula_count
        + report.standard_refs
    )
    if key_elements_original > 0:
        report.info_retention = round(min(key_elements_cleaned / key_elements_original, 1.0), 4)
    else:
        # 无关键元素时，用压缩比的倒数估算
        report.info_retention = round(min(1.0, report.compression_ratio * 1.5), 4)

    return report


def evaluate_batch(
    file_pairs: list[tuple[str, str, str]],
    glossary_path: Optional[str] = None,
) -> BatchDensityReport:
    """批量评估信息密度。

    Args:
        file_pairs: [(filename, original_text, cleaned_text), ...]
        glossary_path: 术语词典路径。

    Returns:
        BatchDensityReport 批量报告。
    """
    batch = BatchDensityReport()
    batch.total_files = len(file_pairs)

    for filename, orig, cleaned in file_pairs:
        report = evaluate_density(orig, cleaned, filename, glossary_path)
        batch.files.append(report)
        batch.total_original_bytes += report.original_size
        batch.total_cleaned_bytes += report.cleaned_size
        batch.total_noise_removed += max(0, report.original_chars - report.cleaned_chars)

    n = len(file_pairs)
    if n > 0:
        batch.avg_compression_ratio = round(
            sum(r.compression_ratio for r in batch.files) / n, 4
        )
        batch.avg_term_density = round(
            sum(r.term_density for r in batch.files) / n, 4
        )
        batch.avg_info_retention = round(
            sum(r.info_retention for r in batch.files) / n, 4
        )

    return batch


def export_report(report: BatchDensityReport, output_path: str, fmt: str = "json"):
    """导出报告到文件。"""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    data = {
        "summary": {
            "total_files": report.total_files,
            "total_original_bytes": report.total_original_bytes,
            "total_cleaned_bytes": report.total_cleaned_bytes,
            "avg_compression_ratio": report.avg_compression_ratio,
            "avg_term_density": report.avg_term_density,
            "avg_info_retention": report.avg_info_retention,
            "total_noise_removed": report.total_noise_removed,
        },
        "files": [
            {
                "filename": r.filename,
                "original_size": r.original_size,
                "cleaned_size": r.cleaned_size,
                "compression_ratio": r.compression_ratio,
                "chinese_ratio": r.chinese_ratio,
                "term_density": r.term_density,
                "heading_count": r.heading_count,
                "table_rows": r.table_rows,
                "code_blocks": r.code_blocks,
                "formula_count": r.formula_count,
                "standard_refs": r.standard_refs,
                "info_retention": r.info_retention,
            }
            for r in report.files
        ],
    }

    if fmt == "json":
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    elif fmt == "csv":
        import csv
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "filename", "original_size", "cleaned_size", "compression_ratio",
                "chinese_ratio", "term_density", "heading_count", "table_rows",
                "code_blocks", "formula_count", "standard_refs", "info_retention",
            ])
            for r in report.files:
                writer.writerow([
                    r.filename, r.original_size, r.cleaned_size, r.compression_ratio,
                    r.chinese_ratio, r.term_density, r.heading_count, r.table_rows,
                    r.code_blocks, r.formula_count, r.standard_refs, r.info_retention,
                ])
