"""文档类型自动检测模块。

通过分析文档内容特征，自动识别文档类型：
  - textbook:  教材（含学习目标、课后习题、案例导入等教学元素）
  - standard:  标准/规范（含标准编号、条款编号、技术参数等）
  - manual:    手册/指南（含操作步骤、注意事项、配置说明等）
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DocTypeResult:
    """文档类型检测结果。"""
    doc_type: str                    # textbook / standard / manual / unknown
    confidence: float                # 0.0 ~ 1.0
    features: dict = field(default_factory=dict)  # 检测到的特征


# ── 特征关键词 ───────────────────────────────────────────────

TEXTBOOK_FEATURES = {
    "learning_objectives": ["学习目标", "学习要求", "教学目标", "能力目标", "知识目标"],
    "exercises": ["课后习题", "课后练习", "思考题", "自测题", "练习题", "实验题", "作业"],
    "case_study": ["案例导入", "案例分析", "案例讨论", "引例"],
    "review": ["本章小结", "本章总结", "本节小结", "要点回顾", "知识拓展"],
    "chapter_structure": ["第[一二三四五六七八九十百千\\d]+章", "第[一二三四五六七八九十百千\\d]+节"],
}

STANDARD_FEATURES = {
    "standard_numbers": [
        "GB[/\\-]", "GB/T", "ISO[/\\-]", "IEC[/\\-]", "IEEE[/\\-]",
        "ANSI", "JIS", "DIN", "BS[/\\-]", "NF[/\\-]",
        "GA[/\\-]", "HB[/\\-]", "YD[/\\-]", "DL[/\\-]", "SJ[/\\-]",
    ],
    "clause_numbers": ["^\\d+(\\.\\d+)+\\s", "^第[一二三四五六七八九十百千\\d]+条"],
    "technical_params": ["技术要求", "技术参数", "性能指标", "技术条件", "规范性引用"],
    "definitions": ["术语和定义", "定义", "术语", "符号和缩略语"],
    "appendix": ["附录\\s*[A-Z]", "规范性附录", "资料性附录"],
}

MANUAL_FEATURES = {
    "procedures": ["操作步骤", "安装步骤", "配置步骤", "使用方法", "操作说明"],
    "warnings": ["注意事项", "警告", "注意", "重要提示", "安全须知", "危险"],
    "config": ["配置文件", "参数设置", "环境变量", "系统要求", "运行环境"],
    "troubleshooting": ["常见问题", "故障排除", "问题排查", "FAQ", "疑难解答"],
    "version": ["版本说明", "更新日志", "发行说明", "Release Notes"],
}


def _count_pattern(text: str, pattern: str) -> int:
    """统计正则模式匹配次数。"""
    return len(re.findall(pattern, text, re.MULTILINE | re.IGNORECASE))


def _count_keywords(text: str, keywords: list[str]) -> int:
    """统计关键词出现总次数。"""
    count = 0
    for kw in keywords:
        count += len(re.findall(re.escape(kw), text, re.IGNORECASE))
    return count


def _count_keyword_group(text: str, keyword_groups: dict[str, list[str]]) -> dict[str, int]:
    """统计每组关键词的匹配次数。"""
    result = {}
    for group_name, keywords in keyword_groups.items():
        total = 0
        for kw in keywords:
            total += len(re.findall(kw, text, re.MULTILINE | re.IGNORECASE))
        result[group_name] = total
    return result


def detect_doc_type(text: str, hint: Optional[str] = None) -> DocTypeResult:
    """检测文档类型。

    Args:
        text: 文档全文内容。
        hint: 可选的类型提示（如文件名中的关键词）。

    Returns:
        DocTypeResult 包含类型、置信度和检测到的特征。
    """
    if not text or len(text.strip()) < 100:
        return DocTypeResult(doc_type="unknown", confidence=0.0, features={})

    # 统计各类型特征
    textbook_features = _count_keyword_group(text, TEXTBOOK_FEATURES)
    standard_features = _count_keyword_group(text, STANDARD_FEATURES)
    manual_features = _count_keyword_group(text, MANUAL_FEATURES)

    textbook_score = sum(textbook_features.values())
    standard_score = sum(standard_features.values())
    manual_score = sum(manual_features.values())

    features = {
        "textbook": textbook_features,
        "standard": standard_features,
        "manual": manual_features,
    }

    # 应用 hint 加权
    if hint:
        hint_lower = hint.lower()
        if any(kw in hint_lower for kw in ["教材", "教程", "课本", "读本"]):
            textbook_score *= 1.5
        elif any(kw in hint_lower for kw in ["标准", "规范", "gb", "iso"]):
            standard_score *= 1.5
        elif any(kw in hint_lower for kw in ["手册", "指南", "说明", "manual", "guide"]):
            manual_score *= 1.5

    total = textbook_score + standard_score + manual_score
    if total == 0:
        return DocTypeResult(doc_type="unknown", confidence=0.0, features=features)

    scores = {
        "textbook": textbook_score,
        "standard": standard_score,
        "manual": manual_score,
    }

    best_type = max(scores, key=scores.get)
    best_score = scores[best_type]
    confidence = round(best_score / total, 3)

    # 低置信度时标记为 unknown
    if confidence < 0.4:
        best_type = "unknown"

    return DocTypeResult(
        doc_type=best_type,
        confidence=confidence,
        features=features,
    )
