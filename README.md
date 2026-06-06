<p align="center">
  <img src="assets/logo.jpg" alt="Doc-Cleaner Logo" width="300">
</p>

<h1 align="center">Doc-Cleaner</h1>

<p align="center">
  <b>智能技术文档清洗工具 — 从技术书籍中提取纯知识，去除一切噪音</b><br>
  <em>Intelligent technical document cleaning tool — extract pure knowledge from technical books, remove all noise</em>
</p>

<p align="center">
  <img src="assets/qq.jpg" alt="QQ 群" width="200">
  <br>
  <em>扫码加入 QQ 群 / Scan to join QQ Group</em>
</p>

---

[English](#english) | [中文](#中文)

---

## English

### What is Doc-Cleaner?

Doc-Cleaner is a CLI tool that strips non-essential content from technical books, standards documents, and training materials — keeping only the knowledge that matters. It handles PDF, DOCX, PPTX, and HTML files, converts them to Markdown, and cleans them using either regex patterns or LLM-powered intelligent extraction.

### Key Features

- **3 cleaning modes**: Fast regex cleaning, LLM intelligent compression, or both combined
- **Dual output**: Each document produces a **Complete Version** (all knowledge preserved) + an **Easy-to-Understand Version** (summarized with examples and analogies)
- **Multi-format input**: PDF, DOCX, PPTX, HTML auto-converted to Markdown via [docling](https://github.com/DS4SD/docling)
- **7 noise categories removed**: Teaching frameworks, historical filler, buzzwords, summary recaps, exercises, footnotes, encoding artifacts
- **Checkpoint & resume**: Interrupt anytime, resume where you left off
- **Rollback system**: Automatic backups before processing, one-command restore
- **Fully configurable**: All behavior driven by `config/default.yaml`

### Quick Start

```bash
# Install
pip install -e .

# Put your files in input/
cp your_book.pdf input/

# Run (default: LLM mode)
doc-cleaner --clean

# Output appears in output/
```

### CLI Commands

| Command | Description |
|---------|-------------|
| `doc-cleaner --clean` | Run cleaning (mode from config) |
| `doc-cleaner --convert` | Convert PDF/DOCX/PPTX/HTML to Markdown only |
| `doc-cleaner --fresh` | Clear output & state, reprocess everything |
| `doc-cleaner --status` | Show processing status |
| `doc-cleaner --rollback --all` | Restore all files from backup |
| `doc-cleaner --rollback --file X` | Restore specific file |
| `doc-cleaner --list-backups` | List all backups |
| `doc-cleaner --export-report` | Export processing report |

### Cleaning Modes

| Mode | Description | Speed | Quality |
|------|-------------|-------|---------|
| `fast` | Regex-based pattern removal | Instant | Basic |
| `llm` | LLM-powered knowledge extraction + summarization | Minutes/file | High |
| `full` | Fast clean first, then LLM compress | Minutes/file | Highest |

### What Gets Removed

1. **Teaching scaffolding**: Learning objectives, chapter summaries, exercises, case introductions
2. **Historical filler**: Timelines, evolution histories, inventor bios
3. **Buzzwords**: "It is worth noting that", "In summary", "As we all know"
4. **Summary recaps**: Key points review, chapter recap
5. **Exercises**: Discussion questions, lab exercises, self-tests
6. **Non-technical footnotes**: Editor notes, translator comments
7. **Encoding noise**: Garbled characters, page breaks, image placeholders

### What Gets Preserved

All technical content: definitions, theorems, formulas, standards references, technical parameters, code examples, table data, step-by-step procedures, comparison analyses.

### Configuration

All settings in `config/default.yaml`:

```yaml
mode: "llm"                          # fast / llm / full

llm:
  api_key: "your-key"                # Or use ${OPENAI_API_KEY}
  base_url: "https://api.deepseek.com"
  model: "deepseek-v4-flash"
  max_chunk_tokens: 1000000          # Max tokens per chunk
  max_output_tokens: 32768           # Max output tokens
  concurrency: 1                     # Parallel file processing
  timeout: 1800                      # Request timeout (seconds)

paths:
  input_dir: "./input"
  output_dir: "./output"
```

Environment variables are supported via `${VAR_NAME}` syntax.

### Project Structure

```
.
├── config/
│   └── default.yaml              # Configuration
├── docs/
│   ├── tutorial_zh.md            # Chinese tutorial
│   └── tutorial_en.md            # English tutorial
├── input/                        # Place files here
├── output/                       # Cleaned files appear here
├── src/
│   └── doc_cleaner/
│       ├── cli.py                # CLI entry point
│       ├── cleaner.py            # Core pipeline
│       ├── converter.py          # PDF/DOCX/HTML → Markdown
│       ├── fast_cleaner.py       # Regex cleaning
│       ├── llm_compressor.py     # LLM extraction
│       ├── doc_type_detector.py  # Document type detection
│       └── info_density.py       # Information density analysis
├── tests/
├── pyproject.toml
└── Makefile
```

### Development

```bash
make install-dev    # Install with dev dependencies
make test           # Run tests
make lint           # Lint & format check
make clean          # Clean build artifacts
```

### License

MIT

---

## 中文

### Doc-Cleaner 是什么？

Doc-Cleaner 是一个命令行工具，用于从技术书籍、标准文档、培训材料中**剥离非核心内容**，只保留真正有用的知识。支持 PDF、DOCX、PPTX、HTML 文件输入，自动转换为 Markdown，然后通过正则或 LLM 进行智能清洗。

### 核心特性

- **3 种清洗模式**：正则快速清洗、LLM 智能压缩、两者组合
- **双版本输出**：每份文档生成**完整版**（保留全部知识）+ **通俗易懂版**（总结+类比+举例）
- **多格式输入**：PDF、DOCX、PPTX、HTML 自动转 Markdown（基于 [docling](https://github.com/DS4SD/docling)）
- **7 类噪音一键清除**：教学框架、历史背景、废话连接词、总结回顾、练习测试、非技术脚注、编码噪声
- **断点续传**：随时中断，下次自动从断点恢复
- **回滚系统**：处理前自动备份，一键恢复
- **全配置驱动**：所有行为通过 `config/default.yaml` 控制

### 快速开始

```bash
# 安装
pip install -e .

# 将文件放入 input/ 目录
cp 你的书籍.pdf input/

# 运行（默认 LLM 模式）
doc-cleaner --clean

# 结果出现在 output/ 目录
```

### 命令速查

| 命令 | 说明 |
|------|------|
| `doc-cleaner --clean` | 执行清洗（模式由配置决定） |
| `doc-cleaner --convert` | 仅转换 PDF/DOCX/PPTX/HTML 为 Markdown |
| `doc-cleaner --fresh` | 清空输出和状态，全部重新处理 |
| `doc-cleaner --status` | 查看处理状态 |
| `doc-cleaner --rollback --all` | 回滚全部文件 |
| `doc-cleaner --rollback --file X` | 回滚指定文件 |
| `doc-cleaner --list-backups` | 查看备份列表 |
| `doc-cleaner --export-report` | 导出处理报告 |

### 清洗模式

| 模式 | 说明 | 速度 | 质量 |
|------|------|------|------|
| `fast` | 基于正则的模式匹配删除 | 秒级 | 基础 |
| `llm` | LLM 智能知识提取 + 总结 | 每文件数分钟 | 高 |
| `full` | 先正则清洗，再 LLM 压缩 | 每文件数分钟 | 最高 |

### 删除的 7 类内容

| 类别 | 示例 |
|------|------|
| 教学框架 | 学习目标、本章小结、课后习题、案例导入 |
| 历史背景 | 发展历程、时间线、发明人介绍 |
| 废话连接词 | 值得一提的是、综上所述、众所周知 |
| 总结回顾 | 本节要点、本章回顾、内容总结 |
| 练习测试 | 思考题、实验题、自测题 |
| 非技术脚注 | 编者按、作者备注、译者注 |
| 编码噪声 | 乱码字符、页面分隔符、图片占位符 |

### 保留的内容

所有技术内容：定义、定理、公式、标准编号、技术参数、代码示例、表格数据、操作步骤、对比分析。

### LLM 双版本输出

在 `llm` 模式下，每份文档自动生成两个版本：

**第一部分：完整版**
- 保留全部知识点、技术细节、代码、公式
- 仅去除格式噪声和重复内容

**第二部分：通俗易懂版**
- 每个概念配一句话定义
- 每个知识点配生活化类比（如"神经网络就像流水线工厂"）
- 每个概念配具体例子
- 关键公式逐符号中文解释

### 配置说明

所有配置在 `config/default.yaml` 中：

```yaml
mode: "llm"                          # fast / llm / full

llm:
  api_key: "your-key"                # 或用 ${OPENAI_API_KEY}
  base_url: "https://api.deepseek.com"
  model: "deepseek-v4-flash"
  max_chunk_tokens: 1000000          # 每块最大 token 数
  max_output_tokens: 32768           # 最大输出 token 数
  concurrency: 1                     # 并发数
  timeout: 1800                      # 请求超时（秒）

paths:
  input_dir: "./input"
  output_dir: "./output"
```

支持 `${VAR_NAME}` 语法引用环境变量。

### 项目结构

```
.
├── config/
│   └── default.yaml              # 配置文件
├── docs/
│   ├── tutorial_zh.md            # 中文教程
│   └── tutorial_en.md            # 英文教程
├── input/                        # 放入待处理文件
├── output/                       # 清洗后的文件
├── src/
│   └── doc_cleaner/
│       ├── cli.py                # CLI 入口
│       ├── cleaner.py            # 核心处理流程
│       ├── converter.py          # PDF/DOCX/HTML → Markdown
│       ├── fast_cleaner.py       # 正则快速清洗
│       ├── llm_compressor.py     # LLM 智能压缩
│       ├── doc_type_detector.py  # 文档类型检测
│       └── info_density.py       # 信息密度评估
├── tests/
├── pyproject.toml
└── Makefile
```

### 开发

```bash
make install-dev    # 安装开发依赖
make test           # 运行测试
make lint           # 代码检查
make clean          # 清理构建产物
```

### 许可证

MIT
