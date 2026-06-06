"""fast_cleaner 模块测试。"""

from doc_cleaner.fast_cleaner import CleanResult, fast_clean


class TestRemoveTeachingFramework:
    """测试教学框架内容删除。"""

    def test_removes_learning_objectives(self, sample_config, textbook_md):
        result = fast_clean(textbook_md, sample_config)
        assert "学习目标" not in result.text

    def test_removes_exercises(self, sample_config, textbook_md):
        result = fast_clean(textbook_md, sample_config)
        assert "课后习题" not in result.text

    def test_removes_summary(self, sample_config, textbook_md):
        result = fast_clean(textbook_md, sample_config)
        assert "本章小结" not in result.text

    def test_preserves_main_content(self, sample_config, textbook_md):
        result = fast_clean(textbook_md, sample_config)
        assert "数据结构" in result.text


class TestRemoveFillerPhrases:
    """测试废话连接词删除。"""

    def test_removes_filler(self, sample_config, noisy_md):
        result = fast_clean(noisy_md, sample_config)
        assert "值得一提的是" not in result.text
        assert "综上所述" not in result.text


class TestRemoveFootnotes:
    """测试非技术脚注删除。"""

    def test_removes_editor_note(self, sample_config, noisy_md):
        result = fast_clean(noisy_md, sample_config)
        assert "编者按" not in result.text


class TestRemoveEncodingNoise:
    """测试编码噪声删除。"""

    def test_removes_html_comments(self, sample_config, noisy_md):
        result = fast_clean(noisy_md, sample_config)
        assert "<!--" not in result.text

    def test_removes_excessive_blank_lines(self, sample_config, noisy_md):
        result = fast_clean(noisy_md, sample_config)
        assert "\n\n\n" not in result.text


class TestProtectBlocks:
    """测试内容块保护。"""

    def test_preserves_code_blocks(self, sample_config):
        md = """# 标题

```python
def hello():
    print("world")
```

正文内容。

综上所述，代码块应保留。
"""
        result = fast_clean(md, sample_config)
        assert "```python" in result.text
        assert 'print("world")' in result.text

    def test_preserves_inline_code(self, sample_config):
        md = """# 标题

使用 `pip install` 命令安装。值得一提的是，这很简单。

正文。
"""
        result = fast_clean(md, sample_config)
        assert "`pip install`" in result.text


class TestCleanResult:
    """测试清洗结果数据结构。"""

    def test_result_fields(self, sample_config, textbook_md):
        result = fast_clean(textbook_md, sample_config)
        assert isinstance(result, CleanResult)
        assert result.original_length > 0
        assert result.cleaned_length > 0
        assert result.cleaned_length <= result.original_length
        assert isinstance(result.removals, dict)

    def test_removals_contain_categories(self, sample_config, textbook_md):
        result = fast_clean(textbook_md, sample_config)
        assert "teaching_framework" in result.removals
        assert "filler_phrases" in result.removals
