"""技术文档智能精简工具 - CLI 入口。

用法:
    doc-cleaner --convert                # 第一步：文档转换（PDF/DOCX -> MD）
    doc-cleaner --clean                  # 第二步：清洗 Markdown
    doc-cleaner --fresh                  # 清除输出和状态，重新清洗
    doc-cleaner --config custom.yaml     # 指定配置文件
    doc-cleaner --convert-formats .pdf   # 指定转换格式
    doc-cleaner --rollback --all         # 回滚全部文件
    doc-cleaner --rollback --file a.md   # 回滚单个文件
    doc-cleaner --list-backups           # 查看备份列表
    doc-cleaner --status                 # 查看处理状态
    doc-cleaner --export-report          # 导出报告
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

from .cleaner import (
    RollbackManager,
    StateManager,
    export_report,
    load_config,
    logger,
    run_convert,
    run_fast_clean,
    run_full_pipeline,
    run_llm_compress,
    setup_logging,
    show_status,
)


def main():
    parser = argparse.ArgumentParser(
        description="技术文档智能精简工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  doc-cleaner --convert                # 第一步：转换（PDF/DOCX -> MD）
  doc-cleaner --clean                  # 第二步：清洗 Markdown
  doc-cleaner --fresh                  # 清除输出和状态，重新清洗
  doc-cleaner --config custom.yaml     # 指定配置文件
  doc-cleaner --convert-formats .pdf   # 指定转换格式
  doc-cleaner --rollback --all         # 回滚全部
  doc-cleaner --rollback --file a.md   # 回滚单个
  doc-cleaner --list-backups           # 查看备份
  doc-cleaner --status                 # 查看状态
  doc-cleaner --export-report          # 导出报告
        """,
    )
    parser.add_argument("--config", default="config/default.yaml", help="配置文件路径 (默认: config/default.yaml)")

    # 转换操作
    parser.add_argument("--convert", action="store_true", help="第一步：文档转换（PDF/DOCX -> MD）")
    parser.add_argument("--convert-formats", type=str, default=None,
                        help="转换格式，逗号分隔 (默认: .pdf,.docx,.pptx,.html,.htm)")

    # 清洗操作
    parser.add_argument("--clean", action="store_true", help="第二步：清洗 Markdown（使用配置中的 mode）")
    parser.add_argument("--fresh", action="store_true", help="清除输出目录和状态文件，重新清洗")

    # 回滚操作
    parser.add_argument("--rollback", action="store_true", help="执行回滚操作")
    parser.add_argument("--all", action="store_true", help="回滚全部文件")
    parser.add_argument("--file", type=str, help="回滚指定文件")

    # 其他操作
    parser.add_argument("--list-backups", action="store_true", help="列出所有备份")
    parser.add_argument("--status", action="store_true", help="查看处理状态")
    parser.add_argument("--export-report", action="store_true", help="导出处理报告")

    args = parser.parse_args()

    # 加载配置
    config = load_config(args.config)

    # 初始化日志
    log_file = setup_logging(config)
    if log_file:
        logger.debug("日志文件: %s", log_file)

    # 初始化核心组件
    paths = config.get("paths", {})
    checkpoint_cfg = config.get("checkpoint", {})
    rollback_cfg = config.get("rollback", {})

    state = StateManager(
        state_file=paths.get("state_file", "./state/process_state.json"),
        enabled=checkpoint_cfg.get("enabled", True),
    )

    rollback = RollbackManager(
        backup_dir=paths.get("backup_dir", "./backups"),
        enabled=rollback_cfg.get("enabled", True),
        max_backups=rollback_cfg.get("max_backups", 100),
        auto_cleanup_days=rollback_cfg.get("auto_cleanup_days", 30),
    )

    # ── 处理命令 ──────────────────────────────────────────────

    if args.list_backups:
        backups = rollback.list_backups()
        if not backups:
            logger.info("没有备份文件")
        else:
            logger.info("=" * 60)
            logger.info("备份列表")
            logger.info("=" * 60)
            for fname, items in backups.items():
                logger.info("  %s (%d 个备份):", fname, len(items))
                for item in items:
                    logger.info("    %s (%d bytes, %s)", item["filename"], item["size"], item["created"])
        return

    if args.status:
        show_status(config, state)
        return

    if args.export_report:
        export_report(config, state)
        return

    # ── 仅转换模式 ──────────────────────────────────────────────

    if args.convert:
        formats = None
        if args.convert_formats:
            formats = [f.strip() for f in args.convert_formats.split(",")]
        run_convert(config, formats=formats)
        return

    # ── 仅清洗模式 ──────────────────────────────────────────────

    if args.rollback:
        if args.all:
            count = rollback.rollback()
            logger.info("已回滚 %d 个文件", count)
        elif args.file:
            count = rollback.rollback(args.file)
            logger.info("已回滚 %d 个文件", count)
        else:
            logger.error("请指定 --all 或 --file <filename>")
        return

    # ── 全新清洗 ──────────────────────────────────────────────

    if args.fresh:
        # 清除输出目录
        output_dir = Path(config["paths"]["output_dir"])
        if output_dir.exists():
            count = len(list(output_dir.glob("**/*.md")))
            for f in output_dir.glob("**/*.md"):
                f.unlink()
            logger.info("已清除输出目录 %d 个 .md 文件", count)
        # 清除输入目录的 .md 文件（转换产物和 chunk 文件）
        input_dir = Path(config["paths"]["input_dir"])
        if input_dir.exists():
            count = len(list(input_dir.glob("**/*.md")))
            for f in input_dir.glob("**/*.md"):
                f.unlink()
            logger.info("已清除输入目录 %d 个 .md 文件", count)
        # 重置状态
        state._state = {"files": {}, "metadata": {"created_at": datetime.now().isoformat(), "last_updated": None, "total_processed": 0, "total_failed": 0}}
        state.save()
        logger.info("已重置状态文件")

    # ── 执行清洗 ──────────────────────────────────────────────

    mode = config.get("mode", "fast")
    logger.info("运行模式: %s", mode)

    # 自动清理过期备份
    rollback.cleanup()

    start_time = time.time()

    if mode == "fast":
        run_fast_clean(config, state, rollback)
    elif mode == "llm":
        run_llm_compress(config, state, rollback)
    elif mode == "full":
        run_full_pipeline(config, state, rollback)
    else:
        logger.error("未知模式: %s (支持: fast / llm / full)", mode)
        sys.exit(1)

    elapsed = time.time() - start_time
    logger.info("总耗时: %.1f 秒", elapsed)

    # 自动导出报告
    if config.get("density", {}).get("enabled", True):
        export_report(config, state)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n用户中断，正在保存状态...")
        sys.exit(0)
    except Exception as e:
        logger.error("程序异常退出: %s: %s", type(e).__name__, e)
        import traceback
        traceback.print_exc()
        sys.exit(1)
