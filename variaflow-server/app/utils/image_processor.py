from __future__ import annotations

import hashlib
import io
from pathlib import Path

from PIL import Image


def _has_transparent_pixels(image: Image.Image) -> bool:
    if image.mode in {"RGBA", "LA"}:
        alpha = image.getchannel("A")
        return alpha.getextrema()[0] < 255

    if image.mode == "P" and "transparency" in image.info:
        converted = image.convert("RGBA")
        alpha = converted.getchannel("A")
        return alpha.getextrema()[0] < 255

    return False


def ensure_transparent_background(image_path: str | Path, temp_root: str | Path) -> Path:
    source_path = Path(image_path)
    temp_dir = Path(temp_root)
    temp_dir.mkdir(parents=True, exist_ok=True)

    with Image.open(source_path) as image:
        if _has_transparent_pixels(image):
            return source_path

    source_bytes = source_path.read_bytes()
    output_name = f"{source_path.stem}_{hashlib.sha1(source_bytes).hexdigest()[:10]}_transparent.png"
    output_path = temp_dir / output_name
    if output_path.exists():
        return output_path

    try:
        from rembg import remove
    except ImportError as exc:
        raise RuntimeError("rembg is required for local background removal") from exc

    result_bytes = remove(source_bytes)
    if not result_bytes:
        raise RuntimeError("rembg returned empty image bytes")

    with Image.open(io.BytesIO(result_bytes)) as result_image:
        rgba_image = result_image.convert("RGBA")
        alpha = rgba_image.getchannel("A")
        if alpha.getextrema()[0] == 255:
            raise RuntimeError("local background removal did not produce transparent pixels")
        rgba_image.save(output_path, format="PNG")

    return output_path
