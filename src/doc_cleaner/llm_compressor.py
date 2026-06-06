"""LLM 智能压缩模块。

调用 LLM API 对 Markdown 文档进行智能压缩与质量提升。
支持：
  - 配置驱动（API密钥、模型、分块大小等从配置文件读取）
  - 失败自动重试（指数退避）
  - 大文件分块处理
  - 并发压缩
"""

import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock
from typing import Optional

logger = logging.getLogger(__name__)


def _resolve_env_var(value: str) -> str:
    """解析配置值中的环境变量引用，如 ${VAR_NAME}。"""
    if not isinstance(value, str):
        return value
    pattern = r'\$\{(\w+)\}'
    def _replace(m):
        var_name = m.group(1)
        return os.environ.get(var_name, m.group(0))
    return re.sub(pattern, _replace, value)


def _estimate_tokens(text: str) -> int:
    """粗略估算 token 数。"""
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    ascii_chars = len(text) - chinese_chars
    return int(chinese_chars * 1.5 + ascii_chars * 0.25)


def _chunk_text(text: str, max_tokens: int = 24000) -> list[str]:
    """按章节分割文本为不超过 max_tokens 的块。"""
    sections = re.split(r'(?=^##\s)', text, flags=re.MULTILINE)
    if len(sections) <= 1:
        sections = re.split(r'(?=^#\s)', text, flags=re.MULTILINE)

    chunks = []
    current = ""
    for section in sections:
        section_tokens = _estimate_tokens(section)
        current_tokens = _estimate_tokens(current)

        if current_tokens + section_tokens > max_tokens and current:
            chunks.append(current.strip())
            current = section
        else:
            current = current + "\n" + section if current else section

    if current.strip():
        chunks.append(current.strip())

    return chunks if chunks else [text]


SYSTEM_PROMPT = """你是一名专业的技术文档编辑，擅长中文技术文档的清洗、知识提取与知识总结。

## 任务

对用户提供的原始 Markdown 文档进行处理，输出一个包含两个部分的 Markdown 文档：
- **第一部分：完整版** — 保留全部知识内容，仅清洗格式噪声
- **第二部分：通俗易懂版** — 对第一部分的知识进行总结、通俗化解释、补充生活化举例

两个部分之间用一条水平分割线（---）隔开。

## ━━━ 第一部分：完整版 ━━━

### 核心原则：知识优先

**绝对不能丢失任何知识内容。** 你的目标是清洗格式噪声，而不是压缩知识。原文中的每一条知识点、每一个技术概念、每一段解释说明都必须保留在输出中。

### 要求

1. **知识完整性（最高优先级）**：
   - 保留所有技术概念的定义、解释、原理说明
   - 保留所有算法/方法的描述、步骤、公式推导
   - 保留所有代码示例和代码片段
   - 保留所有案例分析的内容（包括案例背景、分析过程、结论）
   - 保留所有操作步骤和实践指导
   - 保留所有对比、优缺点分析
   - 保留所有图表的数据和含义说明
   - 仅去除明显的重复段落（逐字重复的内容）

2. **格式清洗**：
   - 移除 PDF 转换产生的噪声（乱码、多余空格、页面分隔符）
   - 修复编码问题
   - 统一中英文标点符号
   - 移除图片占位符注释（<!-- image -->）

3. **结构优化**：
   - 确保标题层级合理
   - 表格、列表格式规范整洁
   - 条款/条文保持清晰编号

4. **适度精简（仅限以下内容）**：
   - 去除纯粹的客套话和出版信息（如"感谢XXX的支持"）
   - 去除广告宣传语句（如"全面精通XXX"）
   - 去除逐字重复的段落
   - 合并分散在多处的相同知识点
   - **不要概括、不要总结、不要省略技术细节**

## ━━━ 第二部分：通俗易懂版 ━━━

### 目标

将第一部分中的所有知识用**通俗易懂**的语言重新组织，让非专业读者也能理解。这一部分不是简单删减，而是**重新表达 + 补充举例**。

### 结构要求

按以下结构组织（每个知识点都要覆盖）：

1. **一句话总结**：用一句话概括本节/本章讲了什么
2. **核心知识点**：列出所有重要概念，每个概念用以下格式：
   - **概念名称**：一句话定义
   - **通俗解释**：用日常类比或比喻解释（比如"神经网络就像一个流水线工厂，原料从一端进去，成品从另一端出来"）
   - **举例**：给出一个具体的生活化例子或应用场景
   - **关键公式**（如有）：列出公式并用中文逐符号解释
3. **实际应用**：总结这些知识在实际中怎么用、能解决什么问题
4. **易混淆点辨析**（如有）：对比容易搞混的概念

### 写作风格

- 语言口语化，像给朋友讲解一样
- 多用"比如"、"想象一下"、"就好比"等引导词
- 避免直接复制第一部分的原文，要用自己的话重新说
- 每个知识点至少一个具体例子

## 输出格式

直接输出完整的 Markdown 内容，结构如下：

```
# 第一部分：完整版

[完整知识内容，保持原文结构和所有技术细节]

---

# 第二部分：通俗易懂版

[总结 + 通俗解释 + 举例，按上述结构组织]
```

不要包含任何元说明、解释或额外标记。
"""


class LLMCompressor:
    """LLM 智能压缩器。"""

    def __init__(self, config: dict):
        llm_cfg = config.get("llm", {})
        self.api_key = _resolve_env_var(llm_cfg.get("api_key", ""))
        self.base_url = llm_cfg.get("base_url", "https://api.deepseek.com")
        self.model = llm_cfg.get("model", "deepseek-v4-flash")
        self.max_chunk_tokens = llm_cfg.get("max_chunk_tokens", 24000)
        self.max_output_tokens = llm_cfg.get("max_output_tokens", 65536)
        self.concurrency = llm_cfg.get("concurrency", 3)
        self.temperature = llm_cfg.get("temperature", 0.1)
        self.retries = llm_cfg.get("retries", 3)
        self.retry_base_delay = llm_cfg.get("retry_base_delay", 2)
        self.timeout = llm_cfg.get("timeout", 1800)  # 请求超时（秒）

        checkpoint_cfg = config.get("checkpoint", {})
        self.max_retries = checkpoint_cfg.get("max_retries", 3)

        if not self.api_key:
            raise ValueError("未设置 LLM API Key，请在配置文件或环境变量 OPENAI_API_KEY 中配置")

        self._client = None

    def _get_client(self):
        """延迟初始化 OpenAI 客户端。"""
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
                timeout=self.timeout,
            )
        return self._client

    def _compress_chunk(self, text: str) -> str:
        """发送单个文本块到 LLM 进行压缩。"""
        if not text.strip():
            return ""

        client = self._get_client()

        for attempt in range(self.retries):
            try:
                resp = client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": text},
                    ],
                    temperature=self.temperature,
                    max_tokens=self.max_output_tokens,
                )
                result = resp.choices[0].message.content.strip()
                # 去除可能的 markdown 代码块包裹
                if result.startswith("```"):
                    result = re.sub(r'^```\w*\n?', '', result)
                    result = re.sub(r'\n?```$', '', result)
                return result
            except Exception as e:
                err_msg = str(e)
                # 不可恢复错误直接抛出
                if any(code in err_msg for code in ["402", "401", "Insufficient Balance"]):
                    raise
                if attempt < self.retries - 1:
                    wait = self.retry_base_delay ** attempt
                    logger.warning("  LLM 重试 %d/%d (%ds): %s", attempt + 1, self.retries, wait, e)
                    time.sleep(wait)
                else:
                    raise

        return ""

    @staticmethod
    def _split_two_parts(text: str) -> tuple[str, str]:
        """将 LLM 输出拆分为完整版和通俗易懂版两部分。

        查找 '# 第二部分' 分隔符，将其前后的文本分开。
        如果找不到分隔符，将全部内容作为完整版，通俗版为空。
        """
        # 匹配 "# 第二部分" 或 "## 第二部分" 等
        match = re.search(r'^#{1,2}\s*第二部分', text, re.MULTILINE)
        if match:
            complete = text[:match.start()].rstrip()
            easy = text[match.start():].strip()
            return complete, easy
        return text.strip(), ""

    def compress_file(self, text: str, filename: str = "") -> tuple[str, dict]:
        """压缩单个文件内容，输出包含完整版+通俗易懂版。

        Args:
            text: 原始 Markdown 文本。
            filename: 文件名（用于日志）。

        Returns:
            (combined_text, stats_dict)
        """
        input_tokens = _estimate_tokens(text)

        if len(text.strip()) < 50:
            return text, {"status": "skipped", "reason": "too short"}

        chunks = _chunk_text(text, self.max_chunk_tokens)

        if len(chunks) == 1:
            logger.info("  [%s] 单块处理 (%d tokens)", filename, input_tokens)
            result = self._compress_chunk(chunks[0])
            complete, easy = self._split_two_parts(result)
        else:
            logger.info("  [%s] 分 %d 块处理 (%d tokens)", filename, len(chunks), input_tokens)
            complete_parts = []
            easy_parts = []
            for i, chunk in enumerate(chunks):
                chunk_tokens = _estimate_tokens(chunk)
                logger.info("    块 %d/%d (%d tokens)", i + 1, len(chunks), chunk_tokens)
                chunk_result = self._compress_chunk(chunk)
                c, e = self._split_two_parts(chunk_result)
                if c:
                    complete_parts.append(c)
                if e:
                    easy_parts.append(e)
            complete = "\n\n".join(complete_parts)
            easy = "\n\n".join(easy_parts)

        # 合并两部分
        if easy:
            combined = complete + "\n\n---\n\n" + easy
        else:
            combined = complete

        output_tokens = _estimate_tokens(combined)
        ratio = output_tokens / input_tokens if input_tokens > 0 else 0

        stats = {
            "status": "completed",
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "chunks": len(chunks),
            "compression_ratio": round(ratio, 4),
        }

        return combined, stats

    def compress_batch(
        self,
        file_contents: dict[str, str],
        state: dict,
        lock: Lock,
    ) -> dict[str, tuple[str, dict]]:
        """批量压缩多个文件。

        Args:
            file_contents: {filename: text_content}
            state: 状态字典（断点续传）。
            lock: 线程锁。

        Returns:
            {filename: (compressed_text, stats)}
        """
        results = {}

        def _process_one(filename: str, text: str) -> tuple[str, str, dict]:
            with lock:
                if state.get(filename, {}).get("status") == "completed":
                    return filename, "", {"status": "skipped", "reason": "already completed"}

            try:
                compressed, stats = self.compress_file(text, filename)
                with lock:
                    state[filename] = stats
                return filename, compressed, stats
            except Exception as e:
                with lock:
                    state[filename] = {"status": "failed", "error": str(e)}
                return filename, "", {"status": "failed", "error": str(e)}

        with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            futures = {
                executor.submit(_process_one, fn, text): fn
                for fn, text in file_contents.items()
                if state.get(fn, {}).get("status") != "completed"
            }

            for i, future in enumerate(as_completed(futures), 1):
                fn, compressed, stats = future.result()
                results[fn] = (compressed, stats)

                if stats["status"] == "completed":
                    logger.info("  [%d/%d] %s: %d -> %d tokens (%.0f%%)",
                                i, len(futures), fn[:50],
                                stats["input_tokens"], stats["output_tokens"],
                                stats["compression_ratio"] * 100)
                elif stats["status"] == "failed":
                    logger.error("  [%d/%d] %s: 失败 - %s", i, len(futures), fn[:50], stats.get("error", ""))
                elif stats["status"] == "skipped":
                    logger.info("  [%d/%d] %s: 跳过 (%s)", i, len(futures), fn[:50], stats.get("reason", ""))

        return results
