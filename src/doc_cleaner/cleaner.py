"""技术文档智能精简工具 - 核心模块。

提供状态管理、回滚系统和主处理流程编排。
"""

from __future__ import annotations

import hashlib
import json
import logging
import logging.handlers
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Optional

import yaml

# ── 自定义日志级别 ──────────────────────────────────────────
STATS_LEVEL = 25  # 介于 INFO(20) 和 WARNING(30) 之间
logging.addLevelName(STATS_LEVEL, "STATS")


class StatsLogger(logging.Logger):
    """支持 STATS 级别的 Logger。"""
    def stats(self, msg, *args, **kwargs):
        if self.isEnabledFor(STATS_LEVEL):
            self._log(STATS_LEVEL, msg, args, **kwargs)


logging.setLoggerClass(StatsLogger)
logger: StatsLogger = logging.getLogger("doc_cleaner")


# ═══════════════════════════════════════════════════════════════
#  配置加载
# ═══════════════════════════════════════════════════════════════

def _resolve_env_vars(obj):
    """递归解析配置中的 ${VAR} 环境变量引用。"""
    if isinstance(obj, str):
        def _replace(m):
            return os.environ.get(m.group(1), m.group(0))
        return re.sub(r'\$\{(\w+)\}', _replace, obj)
    elif isinstance(obj, dict):
        return {k: _resolve_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_resolve_env_vars(item) for item in obj]
    return obj


def load_config(config_path: str) -> dict:
    """加载 YAML 配置文件。"""
    path = Path(config_path)
    if not path.exists():
        print(f"配置文件不存在: {config_path}")
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    return _resolve_env_vars(config)


# ═══════════════════════════════════════════════════════════════
#  日志系统
# ═══════════════════════════════════════════════════════════════

def setup_logging(config: dict) -> str:
    """配置日志系统。

    同时输出到控制台和文件，支持日志轮转。
    返回日志文件路径。
    """
    log_cfg = config.get("logging", {})
    log_dir = Path(config.get("paths", {}).get("log_dir", "./logs"))
    log_dir.mkdir(parents=True, exist_ok=True)

    level = getattr(logging, log_cfg.get("level", "INFO").upper(), logging.INFO)
    fmt = log_cfg.get("format", "[%(asctime)s] %(levelname)-7s %(message)s")
    datefmt = log_cfg.get("datefmt", "%Y-%m-%d %H:%M:%S")
    rotation = log_cfg.get("rotation", {})

    logger.setLevel(min(level, logging.DEBUG))
    formatter = logging.Formatter(fmt, datefmt=datefmt)

    # 控制台输出
    if log_cfg.get("console", True):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # 文件输出（轮转）
    if log_cfg.get("file", True):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"cleaner_{timestamp}.log"
        file_handler = logging.handlers.RotatingFileHandler(
            str(log_file),
            maxBytes=rotation.get("max_bytes", 10 * 1024 * 1024),
            backupCount=rotation.get("backup_count", 5),
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        return str(log_file)

    return ""


# ═══════════════════════════════════════════════════════════════
#  状态管理（断点续传）
# ═══════════════════════════════════════════════════════════════

class StateManager:
    """处理状态管理器，支持断点续传。"""

    def __init__(self, state_file: str, enabled: bool = True):
        self.state_file = Path(state_file)
        self.enabled = enabled
        self.lock = Lock()
        self._state = self._load()

    def _load(self) -> dict:
        """加载状态文件。"""
        if not self.enabled:
            return {"files": {}, "metadata": {}}
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                logger.warning("状态文件损坏，将重新创建: %s", self.state_file)
        return {
            "files": {},
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "last_updated": None,
                "total_processed": 0,
                "total_failed": 0,
            },
        }

    def save(self):
        """保存状态到文件。"""
        if not self.enabled:
            return
        self._state["metadata"]["last_updated"] = datetime.now().isoformat()
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with self.lock:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self._state, f, ensure_ascii=False, indent=2)

    def is_completed(self, filename: str, mode: str | None = None) -> bool:
        """检查文件是否已处理完成。mode 不同时不算完成。"""
        info = self._state.get("files", {}).get(filename, {})
        if info.get("status") != "completed":
            return False
        if mode and info.get("mode") != mode:
            return False
        return True

    def mark_completed(self, filename: str, stats: dict, mode: str | None = None):
        """标记文件为已完成。"""
        with self.lock:
            entry = {
                "status": "completed",
                "timestamp": datetime.now().isoformat(),
                **stats,
            }
            if mode:
                entry["mode"] = mode
            self._state.setdefault("files", {})[filename] = entry
            self._state["metadata"]["total_processed"] = (
                self._state["metadata"].get("total_processed", 0) + 1
            )

    def mark_failed(self, filename: str, error: str, retries: int = 0):
        """标记文件为失败。"""
        with self.lock:
            self._state.setdefault("files", {})[filename] = {
                "status": "failed",
                "timestamp": datetime.now().isoformat(),
                "error": error,
                "retries": retries,
            }
            self._state["metadata"]["total_failed"] = (
                self._state["metadata"].get("total_failed", 0) + 1
            )

    def mark_in_progress(self, filename: str):
        """标记文件为处理中。"""
        with self.lock:
            self._state.setdefault("files", {})[filename] = {
                "status": "in_progress",
                "timestamp": datetime.now().isoformat(),
            }

    def get_status(self) -> dict:
        """获取完整状态。"""
        return self._state

    def get_file_status(self, filename: str) -> dict:
        """获取单个文件的状态。"""
        return self._state.get("files", {}).get(filename, {})

    def get_failed_files(self) -> list[str]:
        """获取所有失败的文件。"""
        return [
            fn for fn, info in self._state.get("files", {}).items()
            if info.get("status") == "failed"
        ]


# ═══════════════════════════════════════════════════════════════
#  回滚系统
# ═══════════════════════════════════════════════════════════════

class RollbackManager:
    """回滚管理器，支持文件备份与恢复。"""

    def __init__(self, backup_dir: str, enabled: bool = True, max_backups: int = 100, auto_cleanup_days: int = 30):
        self.backup_dir = Path(backup_dir)
        self.enabled = enabled
        self.max_backups = max_backups
        self.auto_cleanup_days = auto_cleanup_days
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def _file_hash(self, filepath: Path) -> str:
        """计算文件 MD5 哈希。"""
        h = hashlib.md5()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()[:8]

    def backup(self, filepath: Path) -> Optional[Path]:
        """备份单个文件。

        Returns:
            备份文件路径，失败返回 None。
        """
        if not self.enabled:
            return None
        if not filepath.exists():
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_hash = self._file_hash(filepath)
        backup_name = f"{filepath.stem}_{timestamp}_{file_hash}{filepath.suffix}"
        backup_path = self.backup_dir / filepath.name / backup_name
        backup_path.parent.mkdir(parents=True, exist_ok=True)

        shutil.copy2(str(filepath), str(backup_path))
        logger.debug("  备份: %s -> %s", filepath.name, backup_path.name)
        return backup_path

    def rollback(self, filename: Optional[str] = None) -> int:
        """回滚文件。

        Args:
            filename: 指定文件名，None 则回滚全部。

        Returns:
            回滚的文件数量。
        """
        count = 0
        if filename:
            file_backup_dir = self.backup_dir / filename
            if not file_backup_dir.exists():
                logger.error("未找到 %s 的备份", filename)
                return 0
            backups = sorted(file_backup_dir.iterdir(), reverse=True)
            if not backups:
                logger.error("未找到 %s 的备份文件", filename)
                return 0
            latest = backups[0]
            logger.info("回滚 %s: 使用备份 %s", filename, latest.name)
            count = 1
        else:
            for file_backup_dir in sorted(self.backup_dir.iterdir()):
                if not file_backup_dir.is_dir():
                    continue
                backups = sorted(file_backup_dir.iterdir(), reverse=True)
                if backups:
                    latest = backups[0]
                    logger.info("回滚 %s: 使用备份 %s", file_backup_dir.name, latest.name)
                    count += 1
        return count

    def list_backups(self) -> dict[str, list[dict]]:
        """列出所有备份。"""
        result = {}
        for file_backup_dir in sorted(self.backup_dir.iterdir()):
            if not file_backup_dir.is_dir():
                continue
            backups = []
            for bp in sorted(file_backup_dir.iterdir(), reverse=True):
                stat = bp.stat()
                backups.append({
                    "filename": bp.name,
                    "size": stat.st_size,
                    "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })
            result[file_backup_dir.name] = backups
        return result

    def cleanup(self):
        """清理过期备份。"""
        if not self.enabled:
            return

        cutoff = time.time() - self.auto_cleanup_days * 86400
        removed = 0

        for file_backup_dir in self.backup_dir.iterdir():
            if not file_backup_dir.is_dir():
                continue
            backups = sorted(file_backup_dir.iterdir())

            for bp in backups:
                if bp.stat().st_mtime < cutoff:
                    bp.unlink()
                    removed += 1

            remaining = sorted(file_backup_dir.iterdir())
            while len(remaining) > self.max_backups:
                remaining[0].unlink()
                remaining.pop(0)
                removed += 1

            if not any(file_backup_dir.iterdir()):
                file_backup_dir.rmdir()

        if removed > 0:
            logger.info("自动清理 %d 个过期备份", removed)

    def restore_file(self, source_file: Path, target_path: Path) -> bool:
        """将备份文件恢复到目标路径。

        Args:
            source_file: 备份文件路径。
            target_path: 恢复目标路径。

        Returns:
            是否成功。
        """
        try:
            shutil.copy2(str(source_file), str(target_path))
            logger.info("  已恢复: %s", target_path.name)
            return True
        except Exception as e:
            logger.error("  恢复失败: %s - %s", target_path.name, e)
            return False


# ═══════════════════════════════════════════════════════════════
#  文档转换
# ═══════════════════════════════════════════════════════════════

_CONVERT_FORMATS = [".pdf", ".docx", ".pptx", ".html", ".htm"]


def _has_non_md_files(input_dir: Path, formats: list[str] | None = None) -> bool:
    """检查输入目录中是否存在非 .md 文件。"""
    fmts = formats or _CONVERT_FORMATS
    for ext in fmts:
        if list(input_dir.rglob(f"*{ext}")):
            return True
    return False


def _auto_convert(config: dict, formats: list[str] | None = None):
    """自动检测并转换输入目录中的非 .md 文件。

    转换后的 .md 文件生成在同一输入目录中，然后再执行清洗。
    """
    from .converter import batch_convert

    convert_cfg = config.get("convert", {})
    if not convert_cfg.get("enabled", True):
        return

    input_dir = Path(config["paths"]["input_dir"])
    fmts = formats or convert_cfg.get("formats", _CONVERT_FORMATS)

    if not _has_non_md_files(input_dir, fmts):
        return

    logger.info("=" * 60)
    logger.info("自动转换: 检测到非 .md 文件，先执行文档转换")
    logger.info("=" * 60)

    batch_convert(
        input_dir=str(input_dir),
        output_dir=str(input_dir),  # 原地生成 .md
        formats=fmts,
        do_ocr=convert_cfg.get("do_ocr", True),
        force_ocr=convert_cfg.get("force_ocr", False),
        device=convert_cfg.get("device", "auto"),
        max_pages=convert_cfg.get("max_pages", 20),
        resume=True,
        image_mode=convert_cfg.get("image_mode", "placeholder"),
        include_furniture=convert_cfg.get("include_furniture", False),
    )


def run_convert(config: dict, formats: list[str] | None = None):
    """仅执行文档转换（不清洗）。"""
    from .converter import batch_convert

    convert_cfg = config.get("convert", {})
    input_dir = config["paths"]["input_dir"]
    fmts = formats or convert_cfg.get("formats", _CONVERT_FORMATS)

    logger.info("=" * 60)
    logger.info("文档转换模式")
    logger.info("输入: %s", input_dir)
    logger.info("格式: %s", fmts)
    logger.info("=" * 60)

    batch_convert(
        input_dir=input_dir,
        output_dir=input_dir,  # 原地生成 .md
        formats=fmts,
        do_ocr=convert_cfg.get("do_ocr", True),
        force_ocr=convert_cfg.get("force_ocr", False),
        device=convert_cfg.get("device", "auto"),
        max_pages=convert_cfg.get("max_pages", 20),
        resume=True,
        image_mode=convert_cfg.get("image_mode", "placeholder"),
        include_furniture=convert_cfg.get("include_furniture", False),
    )


# ═══════════════════════════════════════════════════════════════
#  主处理流程
# ═══════════════════════════════════════════════════════════════

def _read_file(filepath: Path) -> str:
    """读取文件，自动处理编码。"""
    for enc in ["utf-8", "gbk", "gb18030", "latin-1"]:
        try:
            with open(filepath, "r", encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def _write_file(filepath: Path, content: str):
    """写入文件。"""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)


def run_fast_clean(config: dict, state: StateManager, rollback: RollbackManager):
    """执行快速清洗流程。"""
    from .fast_cleaner import fast_clean

    input_dir = Path(config["paths"]["input_dir"])
    output_dir = Path(config["paths"]["output_dir"])
    checkpoint_cfg = config.get("checkpoint", {})

    if not input_dir.exists():
        logger.error("输入目录不存在: %s", input_dir)
        return

    md_files = sorted(input_dir.glob("**/*.md"))
    if not md_files:
        logger.warning("输入目录中没有 .md 文件: %s", input_dir)
        return

    logger.info("=" * 60)
    logger.info("快速清洗模式")
    logger.info("输入: %s (%d 个文件)", input_dir, len(md_files))
    logger.info("输出: %s", output_dir)
    logger.info("=" * 60)

    output_dir.mkdir(parents=True, exist_ok=True)
    completed = 0
    skipped = 0
    failed = 0
    interval = checkpoint_cfg.get("interval", 5)

    try:
        from tqdm import tqdm
        file_iter = tqdm(md_files, desc="快速清洗", unit="file")
    except ImportError:
        file_iter = md_files

    for i, filepath in enumerate(file_iter, 1):
        filename = filepath.name

        # 断点续传：跳过已完成的文件
        if state.is_completed(filename, mode="fast"):
            skipped += 1
            logger.debug("  [SKIP] %s 已完成", filename)
            continue

        try:
            # 标记处理中
            state.mark_in_progress(filename)

            # 备份原文件
            rollback.backup(filepath)

            # 读取并清洗
            original = _read_file(filepath)
            result = fast_clean(original, config)

            # 写入输出
            output_path = output_dir / filename
            _write_file(output_path, result.text)

            # 记录统计
            stats = {
                "original_length": result.original_length,
                "cleaned_length": result.cleaned_length,
                "compression_ratio": round(result.cleaned_length / result.original_length, 4) if result.original_length > 0 else 0,
                "removals": result.removals,
                "total_removed": sum(result.removals.values()),
            }
            state.mark_completed(filename, stats, mode="fast")
            completed += 1

            logger.info("  [OK] %s: %d -> %d 字符 (删除 %d)",
                        filename, result.original_length, result.cleaned_length,
                        stats["total_removed"])

        except Exception as e:
            failed += 1
            retries = checkpoint_cfg.get("max_retries", 3)
            state.mark_failed(filename, str(e), retries=retries)
            logger.error("  [FAIL] %s: %s", filename, e)

        # 定期保存状态
        if i % interval == 0:
            state.save()

    # 最终保存
    state.save()

    logger.stats("=" * 60)
    logger.stats("快速清洗完成")
    logger.stats("  完成: %d | 跳过: %d | 失败: %d | 总计: %d", completed, skipped, failed, len(md_files))
    logger.stats("=" * 60)


def run_llm_compress(config: dict, state: StateManager, rollback: RollbackManager):
    """执行 LLM 压缩流程。"""
    from .llm_compressor import LLMCompressor

    input_dir = Path(config["paths"]["input_dir"])
    output_dir = Path(config["paths"]["output_dir"])
    checkpoint_cfg = config.get("checkpoint", {})

    if not input_dir.exists():
        logger.error("输入目录不存在: %s", input_dir)
        return

    md_files = sorted(input_dir.glob("**/*.md"))
    if not md_files:
        logger.warning("输入目录中没有 .md 文件: %s", input_dir)
        return

    logger.info("=" * 60)
    logger.info("LLM 压缩模式")
    logger.info("输入: %s (%d 个文件)", input_dir, len(md_files))
    logger.info("输出: %s", output_dir)
    logger.info("=" * 60)

    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        compressor = LLMCompressor(config)
    except ValueError as e:
        logger.error("初始化失败: %s", e)
        return

    from threading import Lock
    lock = Lock()

    # 加载状态
    file_contents = {}
    for filepath in md_files:
        filename = filepath.name
        if state.is_completed(filename, mode="llm"):
            logger.debug("  [SKIP] %s 已完成", filename)
            continue
        file_contents[filename] = _read_file(filepath)
        rollback.backup(filepath)

    if not file_contents:
        logger.info("所有文件已处理完成")
        return

    logger.info("待处理: %d 个文件", len(file_contents))

    completed = 0
    failed = 0

    for i, (filename, text) in enumerate(file_contents.items(), 1):
        logger.info("  [%d/%d] 处理中: %s", i, len(file_contents), filename[:60])
        try:
            compressed, stats = compressor.compress_file(text, filename)
            if stats["status"] == "completed":
                output_path = output_dir / filename
                _write_file(output_path, compressed)
                state.mark_completed(filename, stats, mode="llm")
                state.save()
                completed += 1
                logger.info("  [%d/%d] ✓ %s: %d -> %d tokens (%.0f%%) [已写入]",
                            i, len(file_contents), filename[:50],
                            stats["input_tokens"], stats["output_tokens"],
                            stats["compression_ratio"] * 100)
            else:
                state.mark_failed(filename, stats.get("error", "unknown"))
                state.save()
                failed += 1
        except Exception as e:
            state.mark_failed(filename, str(e))
            state.save()
            failed += 1
            logger.error("  [%d/%d] ✗ %s: %s", i, len(file_contents), filename[:50], e)

    state.save()

    logger.stats("=" * 60)
    logger.stats("LLM 压缩完成")
    logger.stats("  完成: %d | 失败: %d | 总计: %d", completed, failed, len(file_contents))
    logger.stats("=" * 60)


def run_full_pipeline(config: dict, state: StateManager, rollback: RollbackManager):
    """执行完整流程：快速清洗 + LLM压缩 + 信息密度评估。"""
    logger.info("=" * 60)
    logger.info("完整流程模式")
    logger.info("=" * 60)

    # 第一步：快速清洗
    logger.info("\n>>> 第一步：快速清洗")
    run_fast_clean(config, state, rollback)

    # 第二步：LLM压缩（使用快速清洗的输出作为输入）
    original_input = config["paths"]["input_dir"]
    fast_output = config["paths"]["output_dir"]

    logger.info("\n>>> 第二步：LLM 压缩")
    config["paths"]["input_dir"] = fast_output
    config["paths"]["output_dir"] = str(Path(fast_output).parent / "llm_compressed")
    run_llm_compress(config, state, rollback)

    # 恢复原始路径
    config["paths"]["input_dir"] = original_input


def show_status(config: dict, state: StateManager):
    """显示处理状态。"""
    status = state.get_status()
    files = status.get("files", {})
    meta = status.get("metadata", {})

    logger.info("=" * 60)
    logger.info("处理状态")
    logger.info("=" * 60)
    logger.info("状态文件: %s", config.get("paths", {}).get("state_file", ""))
    logger.info("创建时间: %s", meta.get("created_at", "N/A"))
    logger.info("最后更新: %s", meta.get("last_updated", "N/A"))
    logger.info("已处理: %d", meta.get("total_processed", 0))
    logger.info("失败: %d", meta.get("total_failed", 0))
    logger.info("-" * 60)

    completed = [f for f, i in files.items() if i.get("status") == "completed"]
    failed = [f for f, i in files.items() if i.get("status") == "failed"]
    in_progress = [f for f, i in files.items() if i.get("status") == "in_progress"]

    if completed:
        logger.info("已完成 (%d):", len(completed))
        for f in completed[:10]:
            info = files[f]
            logger.info("  %s (%.1f%% 压缩)", f, info.get("compression_ratio", 0) * 100)
        if len(completed) > 10:
            logger.info("  ... 等 %d 个文件", len(completed) - 10)

    if failed:
        logger.info("失败 (%d):", len(failed))
        for f in failed:
            info = files[f]
            logger.info("  %s: %s (重试 %d)", f, info.get("error", ""), info.get("retries", 0))

    if in_progress:
        logger.info("处理中 (%d):", len(in_progress))
        for f in in_progress:
            logger.info("  %s", f)


def export_report(config: dict, state: StateManager):
    """导出处理报告。"""
    report_dir = Path(config.get("paths", {}).get("report_dir", "./reports"))
    report_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = report_dir / f"report_{timestamp}.json"

    status = state.get_status()
    report = {
        "generated_at": datetime.now().isoformat(),
        "config_summary": {
            "mode": config.get("mode", "unknown"),
            "input_dir": config.get("paths", {}).get("input_dir", ""),
            "output_dir": config.get("paths", {}).get("output_dir", ""),
        },
        **status,
    }

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info("报告已导出: %s", report_path)
    return str(report_path)
