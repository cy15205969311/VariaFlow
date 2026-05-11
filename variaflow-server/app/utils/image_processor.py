from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

RMBG_BYPASS_SKU_CATEGORIES = {
    "real_human_model",
}
TOP_ALIGNED_SKU_CATEGORIES = {
    "apparel_hanging",
}
BOTTOM_ALIGNED_SKU_CATEGORIES = {
    "shoes_resting",
    "real_human_model",
    "toy_standing",
    "appliance_standing",
}
DEFAULT_CANVAS_SIZE = (1024, 1024)
DEFAULT_LAYOUT_CONFIG = {
    "anchor": "bottom_center",
    "max_width_ratio": 0.66,
    "max_height_ratio": 0.60,
    "margin_x_ratio": 0.08,
    "margin_y_ratio": 0.06,
}
SKU_LAYOUT_CONFIGS = {
    "apparel_flat": {
        "anchor": "bottom_center",
        "max_width_ratio": 0.74,
        "max_height_ratio": 0.58,
    },
    "apparel_hanging": {
        "anchor": "top_center",
        "max_width_ratio": 0.56,
        "max_height_ratio": 0.76,
    },
    "apparel_invisible_mannequin": {
        "anchor": "center_right",
        "max_width_ratio": 0.54,
        "max_height_ratio": 0.78,
    },
    "shoes_resting": {
        "anchor": "bottom_right",
        "max_width_ratio": 0.56,
        "max_height_ratio": 0.44,
    },
    "bag_standing": {
        "anchor": "bottom_center",
        "max_width_ratio": 0.48,
        "max_height_ratio": 0.60,
    },
    "accessories_flat": {
        "anchor": "bottom_center",
        "max_width_ratio": 0.60,
        "max_height_ratio": 0.44,
    },
    "beauty_bottle_standing": {
        "anchor": "bottom_center",
        "max_width_ratio": 0.34,
        "max_height_ratio": 0.60,
    },
    "beauty_tube_flat": {
        "anchor": "bottom_right",
        "max_width_ratio": 0.46,
        "max_height_ratio": 0.34,
    },
    "beauty_palette_open": {
        "anchor": "bottom_center",
        "max_width_ratio": 0.52,
        "max_height_ratio": 0.42,
    },
    "jewelry_macro_display": {
        "anchor": "bottom_center",
        "max_width_ratio": 0.24,
        "max_height_ratio": 0.28,
    },
    "watch_stand_display": {
        "anchor": "bottom_center",
        "max_width_ratio": 0.30,
        "max_height_ratio": 0.42,
    },
    "electronic_flat": {
        "anchor": "bottom_center",
        "max_width_ratio": 0.60,
        "max_height_ratio": 0.42,
    },
    "appliance_standing": {
        "anchor": "bottom_center",
        "max_width_ratio": 0.50,
        "max_height_ratio": 0.64,
    },
    "furniture_room_setup": {
        "anchor": "bottom_center",
        "max_width_ratio": 0.80,
        "max_height_ratio": 0.72,
    },
    "home_decor_resting": {
        "anchor": "bottom_right",
        "max_width_ratio": 0.48,
        "max_height_ratio": 0.44,
    },
    "food_packaged_standing": {
        "anchor": "bottom_center",
        "max_width_ratio": 0.42,
        "max_height_ratio": 0.56,
    },
    "food_plated": {
        "anchor": "bottom_center",
        "max_width_ratio": 0.60,
        "max_height_ratio": 0.42,
    },
    "toy_standing": {
        "anchor": "bottom_center",
        "max_width_ratio": 0.46,
        "max_height_ratio": 0.58,
    },
    "plush_sitting": {
        "anchor": "bottom_center",
        "max_width_ratio": 0.52,
        "max_height_ratio": 0.52,
    },
    "virtual_ip_character": {
        "anchor": "center_right",
        "max_width_ratio": 0.44,
        "max_height_ratio": 0.70,
    },
    "real_human_model": {
        "anchor": "bottom_center",
        "max_width_ratio": 0.50,
        "max_height_ratio": 0.82,
    },
    "bottle_standing": {
        "anchor": "bottom_center",
        "max_width_ratio": 0.38,
        "max_height_ratio": 0.60,
    },
    "box_standing": {
        "anchor": "bottom_right",
        "max_width_ratio": 0.50,
        "max_height_ratio": 0.58,
    },
    "3d_toy": {
        "anchor": "bottom_center",
        "max_width_ratio": 0.48,
        "max_height_ratio": 0.62,
    },
    "other_flat": {
        "anchor": "bottom_center",
        "max_width_ratio": 0.68,
        "max_height_ratio": 0.58,
    },
}
SCENE_LAYOUT_OVERRIDES = {
    "old_money_vintage": {
        "anchor": "bottom_right",
        "max_width_ratio": 0.62,
        "max_height_ratio": 0.56,
    },
    "clean_fit_minimal": {
        "anchor": "bottom_center",
        "max_width_ratio": 0.58,
        "max_height_ratio": 0.56,
    },
    "cozy_winter_morning": {
        "anchor": "bottom_center",
        "max_width_ratio": 0.70,
        "max_height_ratio": 0.62,
    },
    "soft_girly_lifestyle": {
        "anchor": "bottom_right",
        "max_width_ratio": 0.56,
        "max_height_ratio": 0.56,
    },
    "natural_skincare_luxury": {
        "anchor": "bottom_center",
        "max_width_ratio": 0.34,
        "max_height_ratio": 0.58,
    },
}


@dataclass(frozen=True, slots=True)
class PreparedSceneEditImage:
    path: Path
    background_removed: bool
    canvas_padded: bool
    anchor: str
    canvas_size: tuple[int, int]
    subject_bbox: tuple[int, int, int, int]
    scale_ratio: float


def _slugify_token(value: str | None, default: str) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return default
    collapsed = "_".join(normalized.split())
    safe_chars = []
    for char in collapsed:
        if char.isalnum() or char in {"_", "-"}:
            safe_chars.append(char)
        else:
            safe_chars.append("_")
    slug = "".join(safe_chars).strip("_")
    return slug or default


def _has_transparent_pixels(image: Image.Image) -> bool:
    if image.mode in {"RGBA", "LA"}:
        alpha = image.getchannel("A")
        return alpha.getextrema()[0] < 255

    if image.mode == "P" and "transparency" in image.info:
        converted = image.convert("RGBA")
        alpha = converted.getchannel("A")
        return alpha.getextrema()[0] < 255

    return False


def _parse_canvas_size(raw_size: str | None) -> tuple[int, int]:
    if not raw_size:
        return DEFAULT_CANVAS_SIZE

    normalized = str(raw_size).strip().lower().replace("*", "x")
    if "x" not in normalized:
        return DEFAULT_CANVAS_SIZE

    width_text, height_text = normalized.split("x", maxsplit=1)
    try:
        width = int(width_text)
        height = int(height_text)
    except ValueError:
        return DEFAULT_CANVAS_SIZE

    if width <= 0 or height <= 0:
        return DEFAULT_CANVAS_SIZE
    return width, height


def _resolve_layout_config(sku_category: str | None, suggested_scene: str | None) -> dict[str, float | str]:
    layout = dict(DEFAULT_LAYOUT_CONFIG)
    layout.update(SKU_LAYOUT_CONFIGS.get(str(sku_category or "").strip().lower(), {}))
    layout.update(SCENE_LAYOUT_OVERRIDES.get(str(suggested_scene or "").strip().lower(), {}))
    return layout


def _compute_paste_offset(
    *,
    canvas_width: int,
    canvas_height: int,
    subject_width: int,
    subject_height: int,
    anchor: str,
    margin_x: int,
    margin_y: int,
) -> tuple[int, int]:
    max_x = max(canvas_width - subject_width - margin_x, margin_x)
    max_y = max(canvas_height - subject_height - margin_y, margin_y)

    if anchor == "bottom_right":
        x = max_x
        y = max_y
    elif anchor == "bottom_left":
        x = margin_x
        y = max_y
    elif anchor == "top_center":
        x = max((canvas_width - subject_width) // 2, margin_x)
        y = margin_y
    elif anchor == "top_right":
        x = max_x
        y = margin_y
    elif anchor == "top_left":
        x = margin_x
        y = margin_y
    elif anchor == "center_right":
        x = max_x
        y = max((canvas_height - subject_height) // 2, margin_y)
    elif anchor == "center_left":
        x = margin_x
        y = max((canvas_height - subject_height) // 2, margin_y)
    else:
        x = max((canvas_width - subject_width) // 2, margin_x)
        y = max_y

    x = min(max(x, 0), max(canvas_width - subject_width, 0))
    y = min(max(y, 0), max(canvas_height - subject_height, 0))
    return x, y


def _compose_subject_on_canvas(
    image_path: str | Path,
    temp_root: str | Path,
    *,
    sku_category: str | None,
    suggested_scene: str | None,
    target_size: str | None,
) -> PreparedSceneEditImage:
    source_path = Path(image_path)
    temp_dir = Path(temp_root)
    temp_dir.mkdir(parents=True, exist_ok=True)

    canvas_width, canvas_height = _parse_canvas_size(target_size)
    layout = _resolve_layout_config(sku_category, suggested_scene)
    anchor = str(layout["anchor"])

    with Image.open(source_path) as image:
        rgba_image = image.convert("RGBA")
        alpha = rgba_image.getchannel("A")
        subject_bbox = alpha.getbbox()
        if subject_bbox is None:
            raise RuntimeError("scene edit source image has no visible subject after preprocessing")

        subject_image = rgba_image.crop(subject_bbox)
        target_width = max(1, int(canvas_width * float(layout["max_width_ratio"])))
        target_height = max(1, int(canvas_height * float(layout["max_height_ratio"])))
        scale_ratio = min(
            target_width / max(subject_image.width, 1),
            target_height / max(subject_image.height, 1),
            1.0,
        )
        resized_width = max(1, int(round(subject_image.width * scale_ratio)))
        resized_height = max(1, int(round(subject_image.height * scale_ratio)))
        resized_subject = subject_image.resize(
            (resized_width, resized_height),
            Image.Resampling.LANCZOS,
        )

    margin_x = int(canvas_width * float(layout["margin_x_ratio"]))
    margin_y = int(canvas_height * float(layout["margin_y_ratio"]))
    paste_x, paste_y = _compute_paste_offset(
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        subject_width=resized_width,
        subject_height=resized_height,
        anchor=anchor,
        margin_x=margin_x,
        margin_y=margin_y,
    )

    canvas = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))
    canvas.paste(resized_subject, (paste_x, paste_y), resized_subject)

    hash_source = source_path.read_bytes()
    output_name = (
        f"{source_path.stem}_{hashlib.sha1(hash_source).hexdigest()[:10]}_"
        f"{_slugify_token(sku_category, 'other_flat')}_{_slugify_token(suggested_scene, 'default')}_canvas.png"
    )
    output_path = temp_dir / output_name
    canvas.save(output_path, format="PNG")

    return PreparedSceneEditImage(
        path=output_path,
        background_removed=False,
        canvas_padded=True,
        anchor=anchor,
        canvas_size=(canvas_width, canvas_height),
        subject_bbox=(paste_x, paste_y, paste_x + resized_width, paste_y + resized_height),
        scale_ratio=scale_ratio,
    )


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


def _should_bypass_background_removal(sku_category: str | None) -> bool:
    return str(sku_category or "").strip().lower() in RMBG_BYPASS_SKU_CATEGORIES


def prepare_scene_edit_source_image(
    image_path: str | Path,
    temp_root: str | Path,
    *,
    sku_category: str | None,
    suggested_scene: str | None,
    target_size: str | None = None,
) -> PreparedSceneEditImage:
    source_path = Path(image_path)
    normalized_sku_category = str(sku_category or "").strip().lower()
    if _should_bypass_background_removal(normalized_sku_category):
        transparent_path = source_path
    else:
        transparent_path = ensure_transparent_background(source_path, temp_root)
    background_removed = transparent_path != source_path

    prepared = _compose_subject_on_canvas(
        transparent_path,
        temp_root,
        sku_category=sku_category,
        suggested_scene=suggested_scene,
        target_size=target_size,
    )

    if background_removed and transparent_path.exists() and transparent_path != prepared.path:
        transparent_path.unlink(missing_ok=True)

    return PreparedSceneEditImage(
        path=prepared.path,
        background_removed=background_removed,
        canvas_padded=prepared.canvas_padded,
        anchor=prepared.anchor,
        canvas_size=prepared.canvas_size,
        subject_bbox=prepared.subject_bbox,
        scale_ratio=prepared.scale_ratio,
    )
