from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError


@dataclass(slots=True)
class QualityCheckResult:
    verdict: str
    fail_codes: list[str]
    min_file_size_ok: bool
    resolution_ok: bool
    mime_type_ok: bool
    width: int | None
    height: int | None
    mime_type: str | None
    file_size_bytes: int

    @property
    def passed(self) -> bool:
        return self.verdict == "passed"

    def to_metrics(self) -> dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "mime_type": self.mime_type,
            "file_size_bytes": self.file_size_bytes,
        }


def run_rules_qc(
    file_path: str,
    min_size: int,
    min_width: int,
    min_height: int,
    allowed_mime_types: set[str] | None = None,
) -> QualityCheckResult:
    """
    执行本地规则质检，返回统一结构化结果。

    质检范围包含：
    - 文件字节数
    - MIME 类型
    - 图片完整性与分辨率
    """

    allowed_types = allowed_mime_types or {"image/png", "image/jpeg", "image/webp"}

    path = Path(file_path)
    fail_codes: list[str] = []
    file_size_bytes = path.stat().st_size
    min_file_size_ok = file_size_bytes >= min_size
    if not min_file_size_ok:
        fail_codes.append("file_too_small")

    mime_type, _ = mimetypes.guess_type(path.name)
    mime_type_ok = mime_type in allowed_types
    if not mime_type_ok:
        fail_codes.append("unsupported_mime_type")

    width: int | None = None
    height: int | None = None
    resolution_ok = False

    try:
        with Image.open(path) as image:
            actual_mime_type = Image.MIME.get(image.format)
            image.verify()
        with Image.open(path) as image:
            width, height = image.size
        if actual_mime_type:
            mime_type = actual_mime_type
        mime_type_ok = mime_type in allowed_types
        if not mime_type_ok and "unsupported_mime_type" not in fail_codes:
            fail_codes.append("unsupported_mime_type")
        resolution_ok = bool(width and height and width >= min_width and height >= min_height)
        if not resolution_ok:
            fail_codes.append("resolution_too_small")
    except (UnidentifiedImageError, OSError):
        fail_codes.append("invalid_image")

    verdict = "passed" if not fail_codes else "failed"
    return QualityCheckResult(
        verdict=verdict,
        fail_codes=fail_codes,
        min_file_size_ok=min_file_size_ok,
        resolution_ok=resolution_ok,
        mime_type_ok=mime_type_ok,
        width=width,
        height=height,
        mime_type=mime_type,
        file_size_bytes=file_size_bytes,
    )


def run_rules_only_qc(file_path: str, config: dict[str, Any]) -> QualityCheckResult:
    """
    兼容旧调用方式的包装函数，内部复用新的规则质检入口。
    """

    return run_rules_qc(
        file_path=file_path,
        min_size=int(config.get("min_file_size_bytes", 51_200)),
        min_width=int(config.get("min_width", 1024)),
        min_height=int(config.get("min_height", 1024)),
        allowed_mime_types=set(config.get("allowed_mime_types", {"image/png", "image/jpeg", "image/webp"})),
    )
