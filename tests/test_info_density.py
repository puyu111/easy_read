"""info_density 模块测试。"""

from doc_cleaner.info_density import (
    BatchDensityReport,
    DensityReport,
    evaluate_batch,
    evaluate_density,
)


class TestEvaluateDensity:
    """测试单文件信息密度评估。"""

    def test_basic_evaluation(self):
        original = "# 标题\n\n这是一段正文内容。\n\n## 小节\n\n更多内容在这里。"
        cleaned = "# 标题\n\n正文内容。"
        report = evaluate_density(original, cleaned, filename="test.md")

        assert isinstance(report, DensityReport)
        assert report.filename == "test.md"
        assert report.original_chars > 0
        assert report.cleaned_chars > 0
        assert report.cleaned_chars <= report.original_chars
        assert 0.0 <= report.compression_ratio <= 1.0

    def test_heading_count(self):
        original = "# H1\n## H2\n### H3\n正文"
        cleaned = "# H1\n## H2\n正文"
        report = evaluate_density(original, cleaned)
        assert report.heading_count == 2

    def test_code_block_count(self):
        original = "正文\n\n```python\ncode\n```\n\n```js\ncode\n```\n\n更多正文"
        cleaned = original
        report = evaluate_density(original, cleaned)
        assert report.code_blocks == 2

    def test_table_rows(self):
        original = "| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |"
        cleaned = original
        report = evaluate_density(original, cleaned)
        assert report.table_rows == 4  # header + separator + 2 data rows

    def test_info_retention_with_elements(self):
        original = "# 标题\n\n正文。\n\n| A | B |\n|---|---|\n| 1 | 2 |"
        cleaned = "# 标题\n\n正文。\n\n| A | B |\n|---|---|\n| 1 | 2 |"
        report = evaluate_density(original, cleaned)
        assert report.info_retention == 1.0

    def test_zero_length_original(self):
        report = evaluate_density("", "some text")
        assert report.compression_ratio == 0.0
        assert report.original_chars == 0


class TestEvaluateBatch:
    """测试批量信息密度评估。"""

    def test_batch_basic(self):
        pairs = [
            ("a.md", "# 标题\n\n正文内容。", "# 标题\n\n正文。"),
            ("b.md", "# 另一个\n\n更多内容。", "# 另一个\n\n内容。"),
        ]
        batch = evaluate_batch(pairs)

        assert isinstance(batch, BatchDensityReport)
        assert batch.total_files == 2
        assert len(batch.files) == 2
        assert batch.avg_compression_ratio > 0

    def test_batch_empty(self):
        batch = evaluate_batch([])
        assert batch.total_files == 0
        assert batch.avg_compression_ratio == 0.0

    def test_batch_noise_removed(self):
        pairs = [
            ("a.md", "很长的原始文本" * 100, "短文本"),
        ]
        batch = evaluate_batch(pairs)
        assert batch.total_noise_removed > 0


class TestDensityReport:
    """测试报告数据结构。"""

    def test_report_fields(self):
        report = evaluate_density("原始文本内容较长一些", "精简后")
        assert isinstance(report, DensityReport)
        assert hasattr(report, "original_size")
        assert hasattr(report, "cleaned_size")
        assert hasattr(report, "chinese_ratio")
        assert hasattr(report, "term_density")
        assert hasattr(report, "standard_refs")
