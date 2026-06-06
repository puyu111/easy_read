"""doc_type_detector 模块测试。"""

from doc_cleaner.doc_type_detector import DocTypeResult, detect_doc_type


class TestDetectTextbook:
    """测试教材类型检测。"""

    def test_detects_textbook(self):
        text = """
# 第一章 数据库基础

## 学习目标
- 理解数据库的基本概念
- 掌握 SQL 语言基础

## 1.1 数据库概述
数据库是按照数据结构来组织、存储和管理数据的仓库。

## 课后习题
1. 什么是数据库？
2. 列举三种常见的数据库类型。

## 本章小结
本章介绍了数据库的基本概念和发展历程。
""" * 3  # 重复以增加文本量
        result = detect_doc_type(text)
        assert result.doc_type == "textbook"
        assert result.confidence > 0.4

    def test_detects_textbook_with_hint(self):
        text = "学习目标 第一章 课后习题 本章小结 案例导入 " * 20
        result = detect_doc_type(text, hint="教材")
        assert result.doc_type == "textbook"


class TestDetectStandard:
    """测试标准/规范类型检测。"""

    def test_detects_standard(self):
        text = """
GB/T 1.1-2020 标准化工作导则

1 范围
本文件规定了标准化文件的结构和起草规则。

2 规范性引用文件
下列文件中的内容通过文中的规范性引用而构成本文件必不可少的条款。

3 术语和定义
下列术语和定义适用于本文件。

4 技术要求
4.1 一般要求
产品应符合以下技术参数要求。
""" * 3
        result = detect_doc_type(text)
        assert result.doc_type == "standard"
        assert result.confidence > 0.4


class TestDetectManual:
    """测试手册/指南类型检测。"""

    def test_detects_manual(self):
        text = """
# 安装指南

## 操作步骤
1. 下载安装包
2. 运行安装程序
3. 按照提示完成安装

## 注意事项
- 请确保系统满足最低要求
- 安装过程中不要关闭计算机

## 常见问题
Q: 安装失败怎么办？
A: 请检查系统要求是否满足。

## 配置文件
编辑 config.yaml 文件进行参数设置。
""" * 3
        result = detect_doc_type(text)
        assert result.doc_type == "manual"
        assert result.confidence > 0.4


class TestDetectUnknown:
    """测试未知类型检测。"""

    def test_empty_text(self):
        result = detect_doc_type("")
        assert result.doc_type == "unknown"
        assert result.confidence == 0.0

    def test_short_text(self):
        result = detect_doc_type("hello world")
        assert result.doc_type == "unknown"

    def test_no_features(self):
        text = "这是一段普通的文本，不包含任何特定的文档类型特征。" * 10
        result = detect_doc_type(text)
        assert result.doc_type == "unknown"


class TestDocTypeResult:
    """测试检测结果结构。"""

    def test_result_fields(self):
        text = "学习目标 课后习题 第一章 本章小结 " * 20
        result = detect_doc_type(text)
        assert isinstance(result, DocTypeResult)
        assert isinstance(result.doc_type, str)
        assert isinstance(result.confidence, float)
        assert isinstance(result.features, dict)
        assert "textbook" in result.features
        assert "standard" in result.features
        assert "manual" in result.features
