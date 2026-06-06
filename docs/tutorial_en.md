# Doc-Cleaner Tutorial

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Installation](#2-installation)
3. [Basic Usage](#3-basic-usage)
4. [Cleaning Modes](#4-cleaning-modes)
5. [LLM Dual Output](#5-llm-dual-output)
6. [Configuration Guide](#6-configuration-guide)
7. [Checkpoint & Rollback](#7-checkpoint--rollback)
8. [Real-World Examples](#8-real-world-examples)
9. [FAQ](#9-faq)

---

## 1. Prerequisites

### System Requirements

- Python 3.10+
- OS: Linux / macOS / Windows (WSL recommended)

### Dependencies

Core dependencies are installed automatically:

| Dependency | Purpose |
|------------|---------|
| `pyyaml` | Configuration parsing |
| `openai` | LLM API calls |
| `tqdm` | Progress bars |
| `docling` | PDF/DOCX/PPTX/HTML to Markdown conversion |
| `pypdf` | Large PDF splitting |

---

## 2. Installation

```bash
# Clone the repository
git clone https://github.com/your-username/ReadBooks.git
cd ReadBooks

# Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install in editable mode
pip install -e .

# Or use Makefile
make install
```

Verify installation:

```bash
doc-cleaner --help
```

---

## 3. Basic Usage

### 3.1 Prepare Input Files

Place files to process in the `input/` directory:

```bash
# Supported formats: PDF, DOCX, PPTX, HTML, Markdown
cp ai_tutorial.pdf input/
cp machine_learning.docx input/
cp deep_learning_notes.md input/
```

### 3.2 Run Cleaning

```bash
# Run with default config (LLM mode)
doc-cleaner --clean

# Use custom config
doc-cleaner --config my_config.yaml --clean
```

### 3.3 View Results

Cleaned files appear in the `output/` directory with the same filenames:

```bash
ls output/
# ai_tutorial.md
# machine_learning.md
# deep_learning_notes.md
```

---

## 4. Cleaning Modes

### 4.1 Fast Mode (fast)

Regex-based pattern matching. Instant processing, good for bulk preprocessing.

```yaml
# config/default.yaml
mode: "fast"
```

**How it works**:
1. Matches 7 noise categories (teaching frameworks, historical filler, etc.)
2. Removes matched content
3. Cleans encoding artifacts and excessive blank lines

**Best for**:
- Bulk preprocessing of many files
- Offline environments (no API needed)
- Quick cleanup before manual editing

### 4.2 LLM Mode (llm)

LLM-powered intelligent knowledge extraction and summarization. Highest quality.

```yaml
# config/default.yaml
mode: "llm"
```

**How it works**:
1. Splits document into chunks by chapter (configurable chunk size)
2. Each chunk is sent to the LLM, producing two parts:
   - **Complete Version**: All knowledge preserved, noise removed
   - **Easy-to-Understand Version**: Summary + analogies + examples
3. All chunks are merged into final output

**Best for**:
- High-quality knowledge extraction
- Creating study-friendly versions
- Removing redundancy while keeping core content

### 4.3 Full Mode (full)

Runs fast cleaning first to remove obvious noise, then LLM for fine extraction.

```yaml
# config/default.yaml
mode: "full"
```

**Workflow**:
```
Raw file → [Fast Clean] → Intermediate → [LLM Compress] → Final Output
```

**Best for**:
- Maximum quality output
- Files with heavy formatting noise
- When you have sufficient time

---

## 5. LLM Dual Output

In `llm` or `full` mode, each file automatically generates two versions separated by `---`:

### Part 1: Complete Version

Preserves all knowledge from the original, with only these modifications:

- Remove garbled characters from PDF conversion
- Remove verbatim duplicate paragraphs
- Remove pleasantries and marketing language
- Normalize punctuation and formatting

**Example output**:

```markdown
# Part 1: Complete Version

## Neural Network Basics

### Neuron Model

A neuron is the basic computational unit of a neural network. Its mathematical model is:

y = Φ(Σxᵢwᵢ + b)

Where:
- xᵢ are input values
- wᵢ are weights
- b is bias
- Φ is the activation function

### Forward Propagation

Forward propagation is the process of computing the network's output:
1. Input data enters the input layer
2. Each layer computes weighted sum: z = Σwᵢxᵢ + b
3. Apply activation function: a = Φ(z)
4. Output passes to the next layer
5. Repeat until output layer
```

### Part 2: Easy-to-Understand Version

Re-explains all concepts in plain language with analogies and examples:

```markdown
# Part 2: Easy-to-Understand Version

## One-Sentence Summary
A neural network is like a factory assembly line — raw materials (data) go in one end, pass through multiple processing stations (layers), and finished products (results) come out the other end.

## Key Concepts

### Neuron Model
- **One-line definition**: A neuron is a "weighted voting machine" that sums up all inputs by importance, then decides whether to "activate"
- **Plain explanation**: Imagine you're voting on where to eat lunch. Each friend (input) has a suggestion (xᵢ), but you trust some friends more (weight wᵢ). You combine everyone's opinions to make a decision
- **Example**: 3 friends recommend restaurants. You trust A most (weight 0.5), then B (0.3), then C (0.2). A says hotpot, B says hotpot, C says BBQ → Weighted score: hotpot 0.8 > BBQ 0.2 → Choose hotpot
- **Formula explained**: y = Φ(Σxᵢwᵢ + b)
  - xᵢ: each friend's suggestion (input value)
  - wᵢ: how much you trust each friend (weight)
  - b: your own preference (bias — e.g., you were already craving spicy food)
  - Φ: your final decision rule (activation function — e.g., "go if score > 0.5")
```

---

## 6. Configuration Guide

Configuration file: `config/default.yaml`

### 6.1 Path Configuration

```yaml
paths:
  input_dir: "./input"              # Input directory
  output_dir: "./output"            # Output directory
  backup_dir: "./backups"           # Backup directory
  state_file: "./state/process_state.json"  # State file (checkpoint)
  log_dir: "./logs"                 # Log directory
  report_dir: "./reports"           # Report directory
```

### 6.2 Run Mode

```yaml
mode: "llm"  # fast / llm / full
```

### 6.3 LLM Configuration

```yaml
llm:
  api_key: "sk-xxx"                 # API key, supports ${ENV_VAR}
  base_url: "https://api.deepseek.com"  # API endpoint
  model: "deepseek-v4-flash"        # Model name
  max_chunk_tokens: 1000000         # Max tokens per chunk
  max_output_tokens: 32768          # Max output tokens
  concurrency: 1                    # Parallel file count
  temperature: 0.1                  # Temperature (lower = more deterministic)
  timeout: 1800                     # Request timeout (seconds)
  retries: 3                        # Retry count
  retry_base_delay: 2               # Retry delay base
```

**Important notes**:
- `max_chunk_tokens` controls whether files are split. Set to 1000000 to disable splitting (good for large files but slower)
- `max_output_tokens` controls max LLM output length. Dual output needs a large value (32768+ recommended)
- `concurrency` of 1 is more stable; 3 can speed up multi-file processing

### 6.4 Document Conversion

```yaml
convert:
  enabled: true                     # Enable auto-conversion
  formats: [".pdf", ".docx", ".pptx", ".html", ".htm"]
  do_ocr: true                      # Enable OCR
  force_ocr: false                  # Force full-page OCR (for scanned docs)
  device: "auto"                    # auto / cuda / cpu
  max_pages: 20                     # Large PDF split threshold
  image_mode: "placeholder"         # Image handling mode
  include_furniture: false          # Include headers/footers
```

### 6.5 Noise Rules

All 7 noise categories are configured in the `rules` section and fully customizable:

```yaml
rules:
  teaching_framework:
    chapter_titles:
      - "学习目标"      # Learning Objectives
      - "课后习题"      # Exercises
      - "案例导入"      # Case Introduction

  filler_phrases:
    - "值得一提的是"    # It is worth noting that
    - "综上所述"        # In summary
    - "众所周知"        # As we all know
```

---

## 7. Checkpoint & Rollback

### 7.1 Checkpoint (Resume)

You can interrupt processing anytime with `Ctrl+C`. Next run automatically resumes from the checkpoint:

```bash
# First run (interrupted after processing 1/3 files)
doc-cleaner --clean
# ^C

# Second run (skips completed files)
doc-cleaner --clean
```

State file: `state/process_state.json`

### 7.2 Rollback

Original files are automatically backed up before processing. Roll back anytime:

```bash
# Rollback all files
doc-cleaner --rollback --all

# Rollback specific file
doc-cleaner --rollback --file "machine_learning.md"

# List all backups
doc-cleaner --list-backups
```

Backup location: `backups/` directory, organized by filename.

### 7.3 Reprocess Everything

```bash
# Clear output and state, reprocess all files
doc-cleaner --fresh
```

---

## 8. Real-World Examples

### Example 1: Clean an AI Textbook

```bash
# 1. Place the file
cp "AI_Training_Manual.pdf" input/

# 2. Run cleaning
doc-cleaner --clean

# 3. View results
head -100 "output/AI_Training_Manual.md"
```

**Processing results**:
- Input: 212,709 tokens
- Output: 11,697 tokens (5.5%)
- Removed: Publishing info, exercises, case introductions, duplicates
- Preserved: All technical concepts, algorithms, code examples, procedures

### Example 2: Batch Process Multiple Books

```bash
# 1. Place multiple files
cp book1.pdf book2.docx book3.md input/

# 2. Process all at once
doc-cleaner --clean

# 3. Check status
doc-cleaner --status
```

### Example 3: Convert Only (No Cleaning)

```bash
# Convert PDF to Markdown without cleaning
doc-cleaner --convert
```

### Example 4: Custom Configuration

```bash
# Use custom config
doc-cleaner --config my_config.yaml --clean
```

---

## 9. FAQ

### Q: Processing is very slow?

**A**: In LLM mode, each file takes several minutes because:
- Large files are sent as single chunks to the API
- Generating dual output (complete + easy version) requires significant output tokens

**Solutions**:
- Reduce `max_chunk_tokens` (e.g., 50000) to split large files into smaller chunks
- Increase `concurrency` (e.g., 3) to process multiple files in parallel

### Q: API error "model not found"?

**A**: Check `model` name in `config/default.yaml`:
- DeepSeek API requires lowercase: `deepseek-v4-flash` (not `DeepSeek-V4-Flash`)
- Verify `base_url` matches the model

### Q: Output file has no Easy-to-Understand version?

**A**: Check if `max_output_tokens` is large enough. Dual output needs significant space — 32768+ recommended.

### Q: How to use my own API?

**A**: Modify the API settings in config:

```yaml
llm:
  api_key: "your-key"
  base_url: "https://your-api-endpoint.com/v1"
  model: "your-model-name"
```

Supports any OpenAI API-compatible service.

### Q: Processing was interrupted?

**A**: Just re-run `doc-cleaner --clean` — it automatically skips completed files. To start fresh, use `doc-cleaner --fresh`.

### Q: How to view the processing report?

```bash
doc-cleaner --export-report
# Report generated in reports/ directory
```
