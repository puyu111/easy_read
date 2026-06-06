"""基于正则的快速清洗模块。

从配置文件读取删除规则，对 Markdown 文档进行快速清洗：
  1. 教学框架（学习目标、课后习题等）
  2. 历史背景（时间线、演进历程等）
  3. 废话连接词（值得一提的是、综上所述等）
  4. 总结回顾（本节要点、本章回顾等）
  5. 练习测试（思考题、实验题等）
  6. 非技术脚注（编者按、作者备注等）
  7. 编码噪声（乱码字符、页面分隔符等）
"""

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class CleanResult:
    """清洗结果。"""
    text: str                                  # 清洗后的文本
    original_length: int = 0                   # 原始字符数
    cleaned_length: int = 0                    # 清洗后字符数
    removals: dict = field(default_factory=dict)  # 各类别删除统计


def _protect_blocks(text: str, preserve_code: bool, preserve_tables: bool, preserve_formulas: bool) -> tuple[str, dict[str, list[str]]]:
    """保护不应被删除的内容块，用占位符替换。

    Returns:
        (替换后文本, {placeholder: original_content})
    """
    placeholders = {}
    counter = [0]

    def _make_placeholder(tag: str, content: str) -> str:
        key = f"__PROTECTED_{tag}_{counter[0]:04d}__"
        counter[0] += 1
        placeholders[key] = content
        return key

    if preserve_code:
        # 保护代码块 ```...```
        def _replace_code(m):
            return _make_placeholder("CODE", m.group(0))
        text = re.sub(r'```[\s\S]*?```', _replace_code, text)
        # 保护行内代码 `...`
        def _replace_inline(m):
            return _make_placeholder("INLINE", m.group(0))
        text = re.sub(r'`[^`\n]+`', _replace_inline, text)

    if preserve_tables:
        # 保护表格行（连续的 | 开头行）
        def _replace_table(m):
            return _make_placeholder("TABLE", m.group(0))
        text = re.sub(r'(?:^\|.*\|$\n?)+', _replace_table, text, flags=re.MULTILINE)

    if preserve_formulas:
        # 保护公式 $$...$$ 和 $...$
        def _replace_display(m):
            return _make_placeholder("FORMULA", m.group(0))
        text = re.sub(r'\$\$[\s\S]*?\$\$', _replace_display, text)
        def _replace_inline_formula(m):
            return _make_placeholder("IFORMULA", m.group(0))
        text = re.sub(r'(?<!\$)\$(?!\$)[^\$\n]+(?<!\$)\$(?!\$)', _replace_inline_formula, text)

    return text, placeholders


def _restore_blocks(text: str, placeholders: dict[str, str]) -> str:
    """恢复被保护的内容块。"""
    for key, original in placeholders.items():
        text = text.replace(key, original)
    return text


def _remove_teaching_framework(text: str, rules: dict) -> tuple[str, int]:
    """删除教学框架内容。"""
    removed = 0
    heading_pattern = rules.get("heading_pattern")
    if heading_pattern:
        # 删除匹配的章节标题及其内容（直到下一个同级或更高级标题）
        def _remove_section(m):
            return ""
        new_text = re.sub(
            r'^#{1,6}\s+.*(?:学习目标|学习要求|本章小结|本章总结|课后习题|课后练习|案例导入|案例分析|知识拓展|拓展阅读|本节小结|学习建议|教学目标|能力目标).*$(?:\n(?!\s*#{1,6}\s).*$)*',
            _remove_section,
            text,
            flags=re.MULTILINE,
        )
        removed += len(text) - len(new_text)
        text = new_text

    return text, removed


def _remove_history(text: str, rules: dict) -> tuple[str, int]:
    """删除历史背景内容。"""
    removed = 0
    heading_pattern = rules.get("heading_pattern")
    if heading_pattern:
        new_text = re.sub(
            r'^#{1,6}\s+.*(?:历史|沿革|发展|演进|起源|背景介绍).*(?:\n(?!\s*#{1,6}\s).*$)*',
            "",
            text,
            flags=re.MULTILINE,
        )
        removed += len(text) - len(new_text)
        text = new_text

    return text, removed


def _remove_filler_phrases(text: str, phrases: list[str]) -> tuple[str, int]:
    """删除废话连接词。"""
    removed = 0
    for phrase in phrases:
        escaped = re.escape(phrase)
        count = len(re.findall(escaped, text))
        if count > 0:
            # 删除短语后，清理残留的标点（如 "，该..." -> "该..."）
            text = re.sub(escaped + r'\s*[，,；;。]', "", text)
            text = re.sub(escaped, "", text)
            removed += count
    return text, removed


def _remove_summary_sections(text: str, rules: dict) -> tuple[str, int]:
    """删除总结回顾内容。"""
    removed = 0
    heading_pattern = rules.get("heading_pattern")
    if heading_pattern:
        new_text = re.sub(
            r'^#{1,6}\s+.*(?:要点|回顾|总结|小结).*(?:\n(?!\s*#{1,6}\s).*$)*',
            "",
            text,
            flags=re.MULTILINE,
        )
        removed += len(text) - len(new_text)
        text = new_text

    return text, removed


def _remove_exercises(text: str, rules: dict) -> tuple[str, int]:
    """删除练习测试内容。"""
    removed = 0
    heading_pattern = rules.get("heading_pattern")
    if heading_pattern:
        new_text = re.sub(
            r'^#{1,6}\s+.*(?:思考题|练习题|实验题|自测题|习题|作业|实训|上机).*(?:\n(?!\s*#{1,6}\s).*$)*',
            "",
            text,
            flags=re.MULTILINE,
        )
        removed += len(text) - len(new_text)
        text = new_text

    return text, removed


def _remove_footnotes(text: str, patterns: list[str]) -> tuple[str, int]:
    """删除非技术脚注。"""
    removed = 0
    for pattern in patterns:
        new_text = re.sub(pattern, "", text, flags=re.MULTILINE)
        removed += len(text) - len(new_text)
        text = new_text
    return text, removed


def _remove_encoding_noise(text: str, rules: dict) -> tuple[str, int]:
    """删除编码噪声。"""
    removed = 0

    # 乱码字符
    garbled = rules.get("garbled_pattern")
    if garbled:
        new_text = re.sub(garbled, "", text)
        removed += len(text) - len(new_text)
        text = new_text

    # Yi音节字符
    yi = rules.get("yi_syllable_pattern")
    if yi:
        new_text = re.sub(yi, "", text)
        removed += len(text) - len(new_text)
        text = new_text

    # 空格分割噪声 "I C S" -> "ICS"
    spaced = rules.get("spaced_letters_pattern")
    if spaced:
        def _fix_spaced(m):
            return m.group(1) + m.group(2) + m.group(3)
        new_text = re.sub(spaced, _fix_spaced, text)
        removed += len(text) - len(new_text)
        text = new_text

    # 页面分隔符
    pagebreak = rules.get("pagebreak_pattern")
    if pagebreak:
        new_text = re.sub(pagebreak, "\n", text, flags=re.IGNORECASE)
        removed += len(text) - len(new_text)
        text = new_text

    # 图片占位符注释
    img = rules.get("img_placeholder_pattern")
    if img:
        new_text = re.sub(img, "", text)
        removed += len(text) - len(new_text)
        text = new_text

    # 连续空行 -> 两个换行
    blank = rules.get("excessive_blank_lines")
    if blank:
        new_text = re.sub(blank, "\n\n", text)
        removed += len(text) - len(new_text)
        text = new_text

    return text, removed


def fast_clean(text: str, config: dict) -> CleanResult:
    """执行快速清洗。

    Args:
        text: 原始 Markdown 文本。
        config: 完整配置字典。

    Returns:
        CleanResult 清洗结果。
    """
    result = CleanResult(text=text, original_length=len(text))

    fast_cfg = config.get("fast_clean", {})
    rules_cfg = config.get("rules", {})

    # 保护代码块、表格、公式
    text, placeholders = _protect_blocks(
        text,
        preserve_code=fast_cfg.get("preserve_code_blocks", True),
        preserve_tables=fast_cfg.get("preserve_tables", True),
        preserve_formulas=fast_cfg.get("preserve_formulas", True),
    )

    # 依次执行各类清洗
    steps = [
        ("teaching_framework", _remove_teaching_framework, rules_cfg.get("teaching_framework", {})),
        ("history", _remove_history, rules_cfg.get("history", {})),
        ("filler_phrases", _remove_filler_phrases, rules_cfg.get("filler_phrases", [])),
        ("summary", _remove_summary_sections, rules_cfg.get("summary", {})),
        ("exercises", _remove_exercises, rules_cfg.get("exercises", {})),
        ("footnotes", _remove_footnotes, rules_cfg.get("footnotes", {}).get("patterns", [])),
        ("encoding_noise", _remove_encoding_noise, rules_cfg.get("encoding_noise", {})),
    ]

    total_removed = 0
    for step_name, step_func, step_config in steps:
        if step_config:
            before = len(text)
            text, removed = step_func(text, step_config)
            result.removals[step_name] = removed
            total_removed += removed
            if removed > 0:
                logger.info("  [%s] 删除 %d 字符", step_name, removed)
        else:
            result.removals[step_name] = 0

    # 自定义正则
    custom_patterns = fast_cfg.get("custom_patterns", [])
    custom_removed = 0
    for pattern in custom_patterns:
        new_text = re.sub(pattern, "", text)
        custom_removed += len(text) - len(new_text)
        text = new_text
    if custom_removed > 0:
        result.removals["custom_patterns"] = custom_removed
        total_removed += custom_removed

    # 恢复被保护的内容块
    text = _restore_blocks(text, placeholders)

    # 最终清理：去除多余空行
    text = re.sub(r'(\n\s*){3,}', '\n\n', text)
    text = text.strip()

    result.text = text
    result.cleaned_length = len(text)
    return result
