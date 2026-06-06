"""测试公共 fixtures。"""

import pytest


@pytest.fixture
def sample_config():
    """最小可用配置。"""
    return {
        "paths": {
            "input_dir": "./input",
            "output_dir": "./output",
            "backup_dir": "./backups",
            "state_file": "./state/process_state.json",
            "log_dir": "./logs",
            "report_dir": "./reports",
        },
        "mode": "fast",
        "logging": {"level": "WARNING", "console": False, "file": False},
        "checkpoint": {"enabled": False},
        "rollback": {"enabled": False},
        "fast_clean": {
            "preserve_code_blocks": True,
            "preserve_tables": True,
            "preserve_formulas": True,
            "custom_patterns": [],
        },
        "rules": {
            "teaching_framework": {
                "heading_pattern": "^#{1,6}\\s+.*(?:学习目标|学习要求|本章小结|本章总结|课后习题|课后练习|案例导入|案例分析|知识拓展|拓展阅读|本节小结|学习建议|教学目标|能力目标)",
            },
            "history": {
                "heading_pattern": "^#{1,6}\\s+.*(?:历史|沿革|发展|演进|起源|背景介绍)",
            },
            "filler_phrases": [
                "值得一提的是",
                "综上所述",
                "总而言之",
                "众所周知",
                "显而易见",
            ],
            "summary": {
                "heading_pattern": "^#{1,6}\\s+.*(?:要点|回顾|总结|小结)",
            },
            "exercises": {
                "heading_pattern": "^#{1,6}\\s+.*(?:思考题|练习题|实验题|自测题|习题|作业|实训|上机)",
            },
            "footnotes": {
                "patterns": [
                    "^\\s*\\[?编者按\\]?[:：]",
                    "^\\s*译者[注按][:：]",
                ],
            },
            "encoding_noise": {
                "garbled_pattern": "[\\x00-\\x08\\x0b\\x0c\\x0e-\\x1f]",
                "yi_syllable_pattern": "[\\uA000-\\uA48F]",
                "spaced_letters_pattern": "\\b([A-Z])\\s([A-Z])\\s([A-Z])\\b",
                "pagebreak_pattern": "---\\s*pagebreak\\s*---",
                "img_placeholder_pattern": "<!--.*?-->",
                "excessive_blank_lines": "(\\n\\s*){3,}",
            },
        },
    }


@pytest.fixture
def textbook_md():
    """包含教学元素的示例 Markdown。"""
    return """# 第一章 数据结构概述

## 1.1 学习目标

- 理解数据结构的基本概念
- 掌握常见数据结构的分类

## 1.2 什么是数据结构

数据结构是计算机科学中的一种组织和存储数据的方式。

## 1.3 课后习题

1. 什么是数据结构？
2. 列举三种常见的数据结构。

## 1.4 本章小结

本章介绍了数据结构的基本概念。
"""


@pytest.fixture
def noisy_md():
    """包含噪声内容的示例 Markdown。"""
    return """# 技术文档

## 正文

这是一个技术文档的正文内容。

<!-- 图片占位符 -->

值得一提的是，这个功能非常有用。

综上所述，我们完成了配置。



编者按：本文档由自动工具生成。

## 操作步骤

执行以下命令即可完成安装。
"""
