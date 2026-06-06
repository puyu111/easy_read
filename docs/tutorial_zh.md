# Doc-Cleaner 使用教程

## 目录

1. [环境准备](#1-环境准备)
2. [安装工具](#2-安装工具)
3. [基本用法](#3-基本用法)
4. [清洗模式详解](#4-清洗模式详解)
5. [LLM 双版本输出](#5-llm-双版本输出)
6. [配置文件详解](#6-配置文件详解)
7. [断点续传与回滚](#7-断点续传与回滚)
8. [实战案例](#8-实战案例)
9. [常见问题](#9-常见问题)

---

## 1. 环境准备

### 系统要求

- Python 3.10+
- 操作系统：Linux / macOS / Windows (WSL 推荐)

### 依赖项

核心依赖会自动安装：

| 依赖 | 用途 |
|------|------|
| `pyyaml` | 配置文件解析 |
| `openai` | LLM API 调用 |
| `tqdm` | 进度条显示 |
| `docling` | PDF/DOCX/PPTX/HTML 转 Markdown |
| `pypdf` | 大 PDF 拆分 |

---

## 2. 安装工具

```bash
# 克隆项目
git clone https://github.com/your-username/ReadBooks.git
cd ReadBooks

# 创建虚拟环境（推荐）
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# 安装（editable 模式，修改代码后无需重新安装）
pip install -e .

# 或使用 Makefile
make install
```

验证安装：

```bash
doc-cleaner --help
```

---

## 3. 基本用法

### 3.1 准备输入文件

将待处理的文件放入 `input/` 目录：

```bash
# 支持的格式：PDF、DOCX、PPTX、HTML、Markdown
cp 人工智能教程.pdf input/
cp 机器学习手册.docx input/
cp 深度学习笔记.md input/
```

### 3.2 运行清洗

```bash
# 使用默认配置运行（LLM 模式）
doc-cleaner --clean

# 指定配置文件
doc-cleaner --config my_config.yaml --clean
```

### 3.3 查看结果

清洗后的文件出现在 `output/` 目录中，文件名与输入相同。

```bash
ls output/
# 人工智能教程.md
# 机器学习手册.md
# 深度学习笔记.md
```

---

## 4. 清洗模式详解

### 4.1 快速清洗模式（fast）

基于正则表达式的模式匹配，速度极快（秒级），适合批量预处理。

```yaml
# config/default.yaml
mode: "fast"
```

**工作原理**：
1. 匹配 7 类噪音模式（教学框架、历史背景等）
2. 删除匹配内容
3. 清理编码噪声和多余空行

**适用场景**：
- 大量文件的初步清洗
- 不需要 LLM 的场景
- 网络环境不佳时

### 4.2 LLM 压缩模式（llm）

调用 LLM API 进行智能知识提取和总结，质量最高。

```yaml
# config/default.yaml
mode: "llm"
```

**工作原理**：
1. 将文档按章节分块（可配置块大小）
2. 每块发送给 LLM，生成两部分内容：
   - **完整版**：保留全部知识，清洗格式噪声
   - **通俗易懂版**：总结 + 类比 + 举例
3. 合并所有块的输出

**适用场景**：
- 需要高质量知识提取
- 需要通俗易懂的学习版本
- 需要去除冗余但保留核心

### 4.3 完整模式（full）

先执行快速清洗去除明显噪音，再用 LLM 精细提取。

```yaml
# config/default.yaml
mode: "full"
```

**工作流程**：
```
原始文件 → [快速清洗] → 中间文件 → [LLM 压缩] → 最终输出
```

**适用场景**：
- 追求最高质量
- 文件包含大量格式噪音
- 有充足的时间

---

## 5. LLM 双版本输出

在 `llm` 或 `full` 模式下，每个文件自动生成两个版本，用 `---` 分隔：

### 第一部分：完整版

保留原文的全部知识内容，仅做以下处理：

- 去除 PDF 转换产生的乱码和噪声
- 去除重复段落（逐字重复的内容）
- 去除客套话和广告宣传
- 统一标点和格式

**示例输出**：

```markdown
# 第一部分：完整版

## 神经网络基础

### 神经元模型

神经元是神经网络的基本计算单元。其数学模型为：

y = Φ(Σxᵢwᵢ + b)

其中：
- xᵢ 为输入值
- wᵢ 为权重
- b 为偏置
- Φ 为激活函数

### 前向传播

前向传播是神经网络计算输出的过程：
1. 输入数据进入输入层
2. 每层计算加权求和：z = Σwᵢxᵢ + b
3. 通过激活函数：a = Φ(z)
4. 输出传递到下一层
5. 重复直到输出层
```

### 第二部分：通俗易懂版

用通俗语言重新解释所有知识点，配类比和举例：

```markdown
# 第二部分：通俗易懂版

## 一句话总结
神经网络就像一个流水线工厂，原料（数据）从一端进去，经过多道工序（层），成品（结果）从另一端出来。

## 核心知识点

### 神经元模型
- **一句话定义**：神经元是一个"加权投票器"，把所有输入按重要性加起来，再决定要不要"激活"
- **通俗解释**：想象你在投票决定中午吃什么。每个朋友（输入）都有不同的建议（xᵢ），但你更信任某些朋友（权重 wᵢ），最后综合大家的意见做决定
- **举例**：3 个朋友推荐餐厅，你最信任 A（权重 0.5），其次 B（权重 0.3），C（权重 0.2）。A 说火锅、B 说火锅、C 说烧烤 → 加权得分：火锅 0.8 > 烧烤 0.2 → 选火锅
- **公式解释**：y = Φ(Σxᵢwᵢ + b)
  - xᵢ：每个朋友的建议（输入值）
  - wᵢ：你对每个朋友的信任度（权重）
  - b：你自己的偏好（偏置，比如你本来就想吃辣）
  - Φ：最终决策规则（激活函数，比如"得分超过 0.5 就去"）
```

---

## 6. 配置文件详解

配置文件位置：`config/default.yaml`

### 6.1 路径配置

```yaml
paths:
  input_dir: "./input"              # 输入目录
  output_dir: "./output"            # 输出目录
  backup_dir: "./backups"           # 备份目录
  state_file: "./state/process_state.json"  # 状态文件（断点续传）
  log_dir: "./logs"                 # 日志目录
  report_dir: "./reports"           # 报告目录
```

### 6.2 运行模式

```yaml
mode: "llm"  # fast / llm / full
```

### 6.3 LLM 配置

```yaml
llm:
  api_key: "sk-xxx"                 # API Key，支持 ${ENV_VAR}
  base_url: "https://api.deepseek.com"  # API 地址
  model: "deepseek-v4-flash"        # 模型名称
  max_chunk_tokens: 1000000         # 每块最大 token 数
  max_output_tokens: 32768          # 最大输出 token 数
  concurrency: 1                    # 并发数
  temperature: 0.1                  # 温度（越低越确定）
  timeout: 1800                     # 请求超时（秒）
  retries: 3                        # 重试次数
  retry_base_delay: 2               # 重试延迟基数
```

**重要提示**：
- `max_chunk_tokens` 决定每个文件是否拆分。设为 1000000 表示不拆分（适合大文件但处理慢）
- `max_output_tokens` 决定 LLM 最大输出长度。双版本输出需要较大值（建议 32768+）
- `concurrency` 设为 1 更稳定，设为 3 可加速处理多个文件

### 6.4 文档转换配置

```yaml
convert:
  enabled: true                     # 启用自动转换
  formats: [".pdf", ".docx", ".pptx", ".html", ".htm"]
  do_ocr: true                      # 启用 OCR
  force_ocr: false                  # 强制全页 OCR（扫描件用）
  device: "auto"                    # auto / cuda / cpu
  max_pages: 20                     # 大 PDF 拆分阈值
  image_mode: "placeholder"         # 图片处理模式
  include_furniture: false          # 是否包含页眉页脚
```

### 6.5 删除规则配置

7 类噪音的匹配规则都在 `rules` 部分，可以自定义：

```yaml
rules:
  teaching_framework:
    chapter_titles:
      - "学习目标"
      - "课后习题"
      - "案例导入"
    heading_pattern: "^#{1,6}\\s+.*(?:学习目标|课后习题|案例导入)"

  history:
    keywords:
      - "发展历程"
      - "历史沿革"

  filler_phrases:
    - "值得一提的是"
    - "综上所述"
    - "众所周知"
```

---

## 7. 断点续传与回滚

### 7.1 断点续传

处理过程中随时可以 `Ctrl+C` 中断，下次运行自动从断点恢复：

```bash
# 第一次运行（处理了 1/3 个文件后中断）
doc-cleaner --clean
# ^C

# 第二次运行（自动跳过已完成的文件）
doc-cleaner --clean
```

状态文件：`state/process_state.json`

### 7.2 回滚

处理前自动备份原始文件，可随时回滚：

```bash
# 回滚全部文件
doc-cleaner --rollback --all

# 回滚指定文件
doc-cleaner --rollback --file "机器学习手册.md"

# 查看备份列表
doc-cleaner --list-backups
```

备份位置：`backups/` 目录，按文件名分目录存放。

### 7.3 重新处理

```bash
# 清空输出和状态，全部重新处理
doc-cleaner --fresh
```

---

## 8. 实战案例

### 案例 1：清洗一本 AI 教材

```bash
# 1. 放入文件
cp "AI训练师手册.pdf" input/

# 2. 运行清洗
doc-cleaner --clean

# 3. 查看结果
head -100 "output/AI训练师手册.md"
```

**处理效果**：
- 原始：212,709 tokens
- 输出：11,697 tokens（5.5%）
- 去除：出版信息、课后习题、案例导入、重复内容
- 保留：全部技术概念、算法描述、代码示例、操作步骤

### 案例 2：批量处理多本书

```bash
# 1. 放入多个文件
cp book1.pdf book2.docx book3.md input/

# 2. 一次处理全部
doc-cleaner --clean

# 3. 查看状态
doc-cleaner --status
```

### 案例 3：仅转换格式（不清洗）

```bash
# 将 PDF 转为 Markdown，不做清洗
doc-cleaner --convert
```

### 案例 4：自定义配置

```bash
# 使用自定义配置
doc-cleaner --config my_config.yaml --clean
```

---

## 9. 常见问题

### Q: 处理速度很慢怎么办？

**A**: LLM 模式下每个文件需要几分钟，原因是：
- 大文件作为单块发送给 API，生成大量输出需要时间
- 可以减小 `max_chunk_tokens`（如 50000）将大文件拆分为小块
- 可以增加 `concurrency`（如 3）同时处理多个文件

### Q: API 报错 "model not found"？

**A**: 检查 `config/default.yaml` 中的 `model` 名称是否正确：
- DeepSeek API 要求小写：`deepseek-v4-flash`（不是 `DeepSeek-V4-Flash`）
- 确认 `base_url` 与模型匹配

### Q: 输出文件没有通俗易懂版？

**A**: 检查 `max_output_tokens` 是否足够。双版本输出需要较大的输出空间，建议至少 32768。

### Q: 如何使用自己的 API？

**A**: 修改配置文件中的 API 设置：

```yaml
llm:
  api_key: "your-key"
  base_url: "https://your-api-endpoint.com/v1"
  model: "your-model-name"
```

支持任何兼容 OpenAI API 格式的服务。

### Q: 处理中断了怎么办？

**A**: 直接重新运行 `doc-cleaner --clean`，会自动跳过已完成的文件。如需全部重来，使用 `doc-cleaner --fresh`。

### Q: 如何查看处理报告？

```bash
doc-cleaner --export-report
# 报告生成在 reports/ 目录
```
