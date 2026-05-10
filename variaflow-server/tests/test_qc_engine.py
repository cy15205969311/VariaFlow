from __future__ import annotations

from pathlib import Path

from PIL import Image

from app.services.qc_engine import run_rules_qc


def _write_png(path: Path, size: tuple[int, int]) -> None:
    image = Image.new("RGBA", size, color=(255, 0, 0, 255))
    image.save(path, format="PNG")


def test_run_rules_qc_accepts_valid_png_with_part_extension(tmp_path: Path) -> None:
    file_path = tmp_path / "generated.part"
    _write_png(file_path, (8, 8))

    result = run_rules_qc(
        str(file_path),
        min_size=1,
        min_width=0,
        min_height=0,
        min_total_pixels=1,
        allowed_mime_types={"image/png"},
    )

    assert result.passed
    assert result.mime_type == "image/png"
    assert result.fail_codes == []


def test_run_rules_qc_uses_total_pixels_for_near_1k_outputs(tmp_path: Path) -> None:
    file_path = tmp_path / "aliyun_output.part"
    _write_png(file_path, (1031, 1015))

    result = run_rules_qc(
        str(file_path),
        min_size=1,
        min_width=0,
        min_height=0,
        min_total_pixels=900_000,
        allowed_mime_types={"image/png"},
    )

    assert result.passed
    assert result.width == 1031
    assert result.height == 1015
