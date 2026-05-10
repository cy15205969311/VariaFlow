from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

from app.utils.image_processor import ensure_transparent_background


def _write_image(path: Path, mode: str, color: tuple[int, ...], image_format: str) -> None:
    image = Image.new(mode, (8, 8), color=color)
    image.save(path, format=image_format)


def test_ensure_transparent_background_returns_original_for_png_with_alpha(tmp_path: Path) -> None:
    source_path = tmp_path / "already_transparent.png"
    _write_image(source_path, "RGBA", (255, 0, 0, 0), "PNG")

    result_path = ensure_transparent_background(source_path, tmp_path / "preprocessed")

    assert result_path == source_path


def test_ensure_transparent_background_runs_rembg_for_opaque_images(
    monkeypatch,
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "opaque.jpg"
    _write_image(source_path, "RGB", (40, 90, 140), "JPEG")

    transparent_buffer = io.BytesIO()
    Image.new("RGBA", (8, 8), (255, 255, 255, 0)).save(transparent_buffer, format="PNG")

    def _fake_remove(image_bytes: bytes) -> bytes:
        assert image_bytes
        return transparent_buffer.getvalue()

    monkeypatch.setattr("rembg.remove", _fake_remove)

    result_path = ensure_transparent_background(source_path, tmp_path / "preprocessed")

    assert result_path != source_path
    assert result_path.suffix.lower() == ".png"
    assert result_path.exists()
    with Image.open(result_path) as result_image:
        assert result_image.mode == "RGBA"
        assert result_image.getchannel("A").getextrema()[0] == 0
