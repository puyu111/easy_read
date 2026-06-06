"""文档转换模块 - 基于 docling 将 PDF/DOCX/PPTX/HTML 转为 Markdown。

支持:
  - 大 PDF 自动拆分（超过阈值分块处理）
  - OCR 开关（对已有文本层的 PDF 可关闭 OCR）
  - 设备选择（CPU / CUDA），GPU OOM 时自动回退到 CPU
  - 跳过已存在的输出（resume）

用法:
    from doc_cleaner.converter import convert_file, batch_convert

    # 转换单个文件
    convert_file("doc.pdf", "./output")

    # 批量转换
    batch_convert("./input", "./output", formats=[".pdf", ".docx"])
"""

from __future__ import annotations

import gc
import logging
import shutil
import tempfile
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger("doc_cleaner")


# ═══════════════════════════════════════════════════════════════
#  GPU 内存管理
# ═══════════════════════════════════════════════════════════════

def _cleanup_gpu_memory() -> None:
    """主动清理 GPU 缓存和 Python 垃圾，防止 GPU OOM。"""
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.synchronize()
            torch.cuda.empty_cache()
    except (ImportError, RuntimeError):
        pass


def _gpu_memory_used_ratio() -> float:
    """返回当前 GPU 显存使用率 (0.0 ~ 1.0)，无 GPU 时返回 0。"""
    try:
        import torch
        if torch.cuda.is_available():
            free, total = torch.cuda.mem_get_info()
            return 1.0 - free / total if total > 0 else 0.0
    except (ImportError, RuntimeError, AttributeError):
        pass
    return 0.0


def _setup_device(device: str) -> str:
    """解析设备参数，返回实际设备名。"""
    if device in ("cpu", "cuda"):
        return device
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
    except ImportError:
        pass
    return "cpu"


# ═══════════════════════════════════════════════════════════════
#  DocumentConverter 构建
# ═══════════════════════════════════════════════════════════════

def _build_converter(
    do_ocr: bool = True,
    force_ocr: bool = False,
    device: str = "auto",
    image_mode: str = "placeholder",
    include_furniture: bool = False,
):
    """构建并返回一个 DocumentConverter 实例。"""
    from docling.document_converter import DocumentConverter, FormatOption
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
    from docling.backend.docling_parse_backend import DoclingParseDocumentBackend

    pipe_opts = PdfPipelineOptions(
        do_ocr=do_ocr,
        force_backend_text=True,
        generate_picture_images=(image_mode != "placeholder"),
    )

    if force_ocr:
        pipe_opts.do_ocr = True
        pipe_opts.force_backend_text = False
        from docling.datamodel.pipeline_options import RapidOcrOptions
        pipe_opts.ocr_options = RapidOcrOptions(
            force_full_page_ocr=True,
            bitmap_area_threshold=0.1,
        )

    if not do_ocr and not force_ocr:
        pipe_opts.force_backend_text = True

    actual_device = _setup_device(device)
    try:
        from docling.datamodel.pipeline_options import AcceleratorDevice
        device_map = {
            "auto": AcceleratorDevice.AUTO,
            "cuda": AcceleratorDevice.CUDA,
            "cpu": AcceleratorDevice.CPU,
        }
        pipe_opts.accelerator_options.device = device_map.get(
            actual_device, AcceleratorDevice.AUTO
        )
    except (ImportError, AttributeError):
        pass

    logger.info("  设备: %s | OCR: %s", actual_device, "强制" if force_ocr else ("开启" if do_ocr else "关闭"))

    fmt = FormatOption(
        pipeline_cls=StandardPdfPipeline,
        backend=DoclingParseDocumentBackend,
        pipeline_options=pipe_opts,
    )
    return DocumentConverter(format_options={InputFormat.PDF: fmt})


# ═══════════════════════════════════════════════════════════════
#  PDF 拆分
# ═══════════════════════════════════════════════════════════════

def _split_pdf(src: Path, max_pages: int, temp_dir: Path) -> List[Path]:
    """用 pypdf 将大 PDF 拆分为多个小 PDF 块。"""
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(str(src))
    total = len(reader.pages)
    chunks: List[Path] = []

    for start in range(0, total, max_pages):
        end = min(start + max_pages, total)
        writer = PdfWriter()
        for i in range(start, end):
            writer.add_page(reader.pages[i])
        chunk_path = temp_dir / f"{src.stem}_p{start + 1:03d}-p{end:03d}.pdf"
        with open(chunk_path, "wb") as f:
            writer.write(f)
        chunks.append(chunk_path)
        logger.info("  拆分块: %s (%d 页)", chunk_path.name, end - start)

    return chunks


def _count_pages_in_pdf(path: Path) -> int:
    """快速获取 PDF 页数。"""
    from pypdf import PdfReader
    return len(PdfReader(str(path)).pages)


# ═══════════════════════════════════════════════════════════════
#  单文件转换
# ═══════════════════════════════════════════════════════════════

def _output_exists(src: Path, output_dir: Path) -> bool:
    """检查目标 .md 文件是否已存在。"""
    return (output_dir / f"{src.stem}.md").exists()


def _convert_single(
    file_path: str,
    output_dir: Path,
    image_mode: str = "placeholder",
    include_furniture: bool = False,
    do_ocr: bool = True,
    force_ocr: bool = False,
    device: str = "auto",
    converter: Optional[object] = None,
) -> str:
    """用 Docling 转换单个文件为 Markdown。

    Returns:
        生成的 .md 文件路径。
    """
    from docling_core.types.doc.base import ImageRefMode

    src = Path(file_path)
    converter_owned = converter is None
    if converter is None:
        converter = _build_converter(do_ocr, force_ocr, device, image_mode, include_furniture)

    logger.info("  转换: %s", src.name)
    result = converter.convert(source=str(src))
    doc = result.document

    img_mode = {
        "placeholder": ImageRefMode.PLACEHOLDER,
        "embedded": ImageRefMode.EMBEDDED,
        "referenced": ImageRefMode.REFERENCED,
    }.get(image_mode, ImageRefMode.PLACEHOLDER)

    export_kwargs: dict = dict(
        image_mode=img_mode,
        escape_html=True,
        escape_underscores=True,
        enable_chart_tables=True,
        include_annotations=True,
        mark_annotations=False,
        compact_tables=False,
        traverse_pictures=True,
    )

    if include_furniture:
        from docling_core.types.doc.document import ContentLayer
        export_kwargs["included_content_layers"] = {
            ContentLayer.BODY,
            ContentLayer.FURNITURE,
            ContentLayer.NOTES,
        }

    full_md = doc.export_to_markdown(**export_kwargs)
    md_name = f"{src.stem}.md"
    md_path = output_dir / md_name
    md_path.write_text(full_md.strip(), encoding="utf-8")
    logger.info("  [OK] %s", md_path.name)

    del doc, result
    if converter_owned:
        del converter
    _cleanup_gpu_memory()

    return str(md_path)


def convert_file(
    file_path: str,
    output_dir: str,
    do_ocr: bool = True,
    force_ocr: bool = False,
    device: str = "auto",
    max_pages: int = 20,
    resume: bool = True,
    image_mode: str = "placeholder",
    include_furniture: bool = False,
) -> List[str]:
    """将单个文件转为 Markdown 并保存。

    Args:
        file_path: 源文件路径。
        output_dir: 输出目录。
        do_ocr: 是否启用 OCR。
        force_ocr: 是否强制全页 OCR。
        device: 推理设备 ("auto", "cuda", "cpu")。
        max_pages: 大 PDF 拆分页数阈值（0=不拆分）。
        resume: 是否跳过已存在的输出。
        image_mode: 图片处理方式 ("placeholder", "embedded", "referenced")。
        include_furniture: 是否包含页眉页脚等装饰性内容。

    Returns:
        生成的 .md 文件路径列表。
    """
    # 静默第三方日志
    for name in ("rapidocr", "docling", "docling.backend.msword_backend"):
        logging.getLogger(name).setLevel(logging.ERROR)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    src = Path(file_path)

    if resume and _output_exists(src, output_path):
        # 清理可能残留的拆分 chunk 文件
        for orphan in output_path.glob(f"{src.stem}_p[0-9]*-p[0-9]*.md"):
            orphan.unlink(missing_ok=True)
        logger.info("  [SKIP] %s 输出已存在，跳过", src.name)
        return [str(output_path / f"{src.stem}.md")]

    # 大 PDF 拆分逻辑
    if max_pages > 0 and src.suffix.lower() == ".pdf":
        temp_dir = None
        generated: List[str] = []
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(src))
            total_pages = len(reader.pages)

            if total_pages > max_pages:
                temp_dir = Path(tempfile.mkdtemp(prefix="pdf_chunks_"))
                chunk_files = _split_pdf(src, max_pages, temp_dir)
                logger.info("  已拆分为 %d 个块 (最多 %d 页/块)，总页数: %d",
                            len(chunk_files), max_pages, total_pages)

                for chunk_path in chunk_files:
                    chunk_md = output_path / f"{chunk_path.stem}.md"
                    if resume and chunk_md.exists():
                        logger.info("  [SKIP] 块 %s 已转换，跳过", chunk_path.name)
                        generated.append(str(chunk_md))
                        continue

                    # GPU 显存检查
                    chunk_device = device
                    chunk_conv = None
                    if device != "cpu" and _gpu_memory_used_ratio() > 0.80:
                        logger.info("  GPU 显存使用率 %.0f%%，此块走 CPU", _gpu_memory_used_ratio() * 100)
                        chunk_device = "cpu"

                    try:
                        chunk_result = _convert_single(
                            str(chunk_path), output_path, image_mode,
                            include_furniture, do_ocr, force_ocr,
                            chunk_device, converter=chunk_conv,
                        )
                        generated.append(chunk_result)
                    except (RuntimeError, MemoryError) as e:
                        err_str = str(e).lower()
                        if chunk_device != "cpu" and ("out of memory" in err_str or "cuda" in err_str):
                            logger.warning("  [OOM] GPU 内存不足，chunk 切换到 CPU 重试...")
                            _cleanup_gpu_memory()
                            chunk_result = _convert_single(
                                str(chunk_path), output_path, image_mode,
                                include_furniture, do_ocr, force_ocr,
                                "cpu", converter=None,
                            )
                            generated.append(chunk_result)
                        else:
                            raise

                # 合并所有 chunk 的 .md
                full_md_parts = []
                for md_path_str in generated:
                    full_md_parts.append(Path(md_path_str).read_text(encoding="utf-8"))
                combined_md = "\n\n--- pagebreak ---\n\n".join(full_md_parts)
                md_path = output_path / f"{src.stem}.md"
                md_path.write_text(combined_md.strip(), encoding="utf-8")
                # 清理 chunk 文件
                for md_path_str in generated:
                    Path(md_path_str).unlink(missing_ok=True)
                shutil.rmtree(temp_dir, ignore_errors=True)
                logger.info("  [OK] %s (合并 %d 页)", md_path.name, total_pages)
                return [str(md_path)]

        except Exception as e:
            logger.warning("  [WARN] PDF 拆分失败 (%s: %s)，将尝试直接转换", type(e).__name__, e)
        finally:
            # 清理拆分产生的 chunk .md 文件
            for md_path_str in generated:
                Path(md_path_str).unlink(missing_ok=True)
            # 清理拆分产生的临时 PDF 文件
            if temp_dir is not None and temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

    # 普通转换
    converter = _build_converter(do_ocr, force_ocr, device, image_mode, include_furniture)
    try:
        return [_convert_single(
            file_path, output_path, image_mode,
            include_furniture, do_ocr, force_ocr,
            device, converter=converter,
        )]
    except (RuntimeError, MemoryError) as e:
        err_str = str(e).lower()
        if device != "cpu" and ("out of memory" in err_str or "cuda" in err_str):
            logger.warning("  [OOM] GPU 内存不足，自动切换到 CPU 重试...")
            _cleanup_gpu_memory()
            return [_convert_single(
                file_path, output_path, image_mode,
                include_furniture, do_ocr, force_ocr,
                "cpu", converter=None,
            )]
        raise
    finally:
        del converter
        _cleanup_gpu_memory()


# ═══════════════════════════════════════════════════════════════
#  批量转换
# ═══════════════════════════════════════════════════════════════

def batch_convert(
    input_dir: str,
    output_dir: str,
    formats: Optional[List[str]] = None,
    do_ocr: bool = True,
    force_ocr: bool = False,
    device: str = "auto",
    max_pages: int = 20,
    resume: bool = True,
    image_mode: str = "placeholder",
    include_furniture: bool = False,
) -> int:
    """批量转换目录下所有文档为 Markdown。

    Args:
        input_dir: 输入目录。
        output_dir: 输出目录。
        formats: 支持的文件扩展名列表。
        do_ocr: 是否启用 OCR。
        force_ocr: 是否强制全页 OCR。
        device: 推理设备。
        max_pages: 大 PDF 拆分阈值。
        resume: 是否跳过已存在的输出。
        image_mode: 图片处理方式。
        include_furniture: 是否包含页眉页脚。

    Returns:
        成功转换的文件数量。
    """
    if formats is None:
        formats = [".pdf", ".docx", ".pptx", ".html", ".htm"]

    input_path = Path(input_dir)
    files = []
    for ext in formats:
        files.extend(input_path.rglob(f"*{ext}"))

    if not files:
        logger.info("在 %s 中未找到 %s 格式的文件", input_dir, formats)
        return 0

    logger.info("找到 %d 个文件，开始转换...", len(files))
    success = 0

    for idx, fp in enumerate(sorted(files)):
        if idx > 0 and idx % 5 == 0:
            _cleanup_gpu_memory()

        if resume and _output_exists(fp, Path(output_dir)):
            logger.info("  [%d/%d] [SKIP] %s 输出已存在", idx + 1, len(files), fp.name)
            success += 1
            continue

        try:
            logger.info("  [%d/%d] 转换: %s", idx + 1, len(files), fp.name)
            convert_file(
                str(fp), output_dir,
                do_ocr=do_ocr, force_ocr=force_ocr,
                device=device, max_pages=max_pages,
                resume=resume, image_mode=image_mode,
                include_furniture=include_furniture,
            )
            success += 1
        except (RuntimeError, MemoryError) as e:
            err_str = str(e).lower()
            if device != "cpu" and ("out of memory" in err_str or "cuda" in err_str):
                logger.warning("  [OOM] %s GPU 内存不足，清空缓存后重试...", fp.name)
                _cleanup_gpu_memory()
                try:
                    convert_file(
                        str(fp), output_dir,
                        do_ocr=do_ocr, force_ocr=force_ocr,
                        device="cpu", max_pages=max_pages,
                        resume=resume, image_mode=image_mode,
                        include_furniture=include_furniture,
                    )
                    success += 1
                except Exception as e2:
                    logger.error("  [FAIL] %s: %s: %s", fp.name, type(e2).__name__, e2)
            else:
                logger.error("  [FAIL] %s: %s: %s", fp.name, type(e).__name__, e)
        except Exception as e:
            logger.error("  [FAIL] %s: %s: %s", fp.name, type(e).__name__, e)

    logger.info("转换完成: %d/%d 个文件成功", success, len(files))
    return success
