"""技术文档智能精简工具。"""

__version__ = "0.1.0"

from .fast_cleaner import fast_clean, CleanResult
from .doc_type_detector import detect_doc_type, DocTypeResult
from .info_density import evaluate_density, DensityReport

__all__ = [
    "fast_clean",
    "CleanResult",
    "detect_doc_type",
    "DocTypeResult",
    "evaluate_density",
    "DensityReport",
]
