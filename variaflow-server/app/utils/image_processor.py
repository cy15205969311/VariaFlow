from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps

RMBG_BYPASS_SKU_CATEGORIES = {
    "real_human_model",
}
AUTO_FRAME_BOTTOM_ALIGNED_SKU_CATEGORIES = {
    "shoes_resting",
    "toy_standing",
    "3d_toy",
    "bottle_standing",
    "beauty_bottle_standing",
    "box_standing",
    "bag_standing",
    "appliance_standing",
    "food_packaged_standing",
    "watch_stand_display",
    "jewelry_macro_display",
}
DEFAULT_CANVAS_SIZE = (1024, 1024)
AUTO_FRAME_DEFAULTS = {
    "anchor": "center",
    "occupancy_ratio": 0.65,
    "margin_x_ratio": 0.08,
    "margin_y_ratio": 0.08,
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
    mask_path: Path | None = None
    mask_generated: bool = False


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


def _resolve_auto_frame_config(
    sku_category: str | None,
    subject_type: str | None,
) -> dict[str, float | str]:
    normalized_sku_category = str(sku_category or "").strip().lower()
    normalized_subject_type = str(subject_type or "").strip().lower()
    layout = dict(AUTO_FRAME_DEFAULTS)

    if normalized_subject_type == "human_model":
        layout.update(
            {
                "anchor": "bottom_center",
                "occupancy_ratio": 0.48,
                "margin_y_ratio": 0.10,
            }
        )
        return layout

    if normalized_sku_category == "apparel_hanging":
        layout.update(
            {
                "anchor": "top_center",
                "occupancy_ratio": 0.50,
                "margin_y_ratio": 0.08,
            }
        )
        return layout

    if normalized_sku_category == "apparel_leaning":
        layout.update(
            {
                "anchor": "bottom_center",
                "occupancy_ratio": 0.52,
                "margin_y_ratio": 0.10,
            }
        )
        return layout

    if normalized_sku_category in AUTO_FRAME_BOTTOM_ALIGNED_SKU_CATEGORIES:
        layout.update(
            {
                "anchor": "bottom_center",
                "occupancy_ratio": 0.40,
                "margin_y_ratio": 0.10,
            }
        )
        return layout

    layout.update(
        {
            "anchor": "center",
            "occupancy_ratio": 0.65,
            "margin_y_ratio": 0.08,
        }
    )
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
    elif anchor == "center":
        x = max((canvas_width - subject_width) // 2, margin_x)
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
    subject_type: str | None,
    suggested_scene: str | None,
    target_size: str | None,
) -> PreparedSceneEditImage:
    source_path = Path(image_path)
    temp_dir = Path(temp_root)
    temp_dir.mkdir(parents=True, exist_ok=True)

    canvas_width, canvas_height = _parse_canvas_size(target_size)
    layout = _resolve_auto_frame_config(sku_category, subject_type)
    anchor = str(layout["anchor"])

    with Image.open(source_path) as image:
        rgba_image = image.convert("RGBA")
        alpha = rgba_image.getchannel("A")
        subject_bbox = alpha.getbbox()
        if subject_bbox is None:
            raise RuntimeError("scene edit source image has no visible subject after preprocessing")

        subject_image = rgba_image.crop(subject_bbox)
        occupancy_ratio = float(layout["occupancy_ratio"])
        target_width = max(1, int(canvas_width * occupancy_ratio))
        target_height = max(1, int(canvas_height * occupancy_ratio))
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


def generate_background_mask(image_path: str | Path, temp_root: str | Path) -> Path:
    source_path = Path(image_path)
    temp_dir = Path(temp_root)
    temp_dir.mkdir(parents=True, exist_ok=True)

    source_bytes = source_path.read_bytes()
    output_name = f"{source_path.stem}_{hashlib.sha1(source_bytes).hexdigest()[:10]}_background_mask.png"
    output_path = temp_dir / output_name
    if output_path.exists():
        return output_path

    try:
        from rembg import remove
    except ImportError as exc:
        raise RuntimeError("rembg is required for local background masking") from exc

    cutout_bytes = remove(source_bytes)
    if not cutout_bytes:
        raise RuntimeError("rembg returned empty image bytes while generating a background mask")

    with Image.open(io.BytesIO(cutout_bytes)) as cutout_image:
        rgba_cutout = cutout_image.convert("RGBA")
        subject_alpha = rgba_cutout.getchannel("A")
        if subject_alpha.getextrema()[1] == 0:
            raise RuntimeError("background masking did not detect any visible subject")

        background_edit_mask = ImageOps.invert(subject_alpha)
        mask_rgba = background_edit_mask.convert("RGBA")
        mask_rgba.putalpha(background_edit_mask)
        mask_rgba.save(output_path, format="PNG")

    return output_path


def ensure_mask_compatible_edit_image(image_path: str | Path, temp_root: str | Path) -> Path:
    source_path = Path(image_path)
    if source_path.suffix.lower() == ".png":
        return source_path

    temp_dir = Path(temp_root)
    temp_dir.mkdir(parents=True, exist_ok=True)
    source_bytes = source_path.read_bytes()
    output_name = f"{source_path.stem}_{hashlib.sha1(source_bytes).hexdigest()[:10]}_mask_edit_source.png"
    output_path = temp_dir / output_name
    if output_path.exists():
        return output_path

    with Image.open(source_path) as image:
        rgba_image = image.convert("RGBA")
        rgba_image.save(output_path, format="PNG")
    return output_path


def _should_bypass_background_removal(sku_category: str | None) -> bool:
    return str(sku_category or "").strip().lower() in RMBG_BYPASS_SKU_CATEGORIES


def _should_bypass_background_removal_for_subject(
    sku_category: str | None,
    subject_type: str | None,
) -> bool:
    normalized_subject_type = str(subject_type or "").strip().lower()
    if normalized_subject_type == "human_model":
        return True
    return _should_bypass_background_removal(sku_category)


def prepare_scene_edit_source_image(
    image_path: str | Path,
    temp_root: str | Path,
    *,
    sku_category: str | None,
    subject_type: str | None = None,
    suggested_scene: str | None,
    target_size: str | None = None,
) -> PreparedSceneEditImage:
    source_path = Path(image_path)
    normalized_sku_category = str(sku_category or "").strip().lower()
    normalized_subject_type = str(subject_type or "").strip().lower()

    if normalized_subject_type == "human_model" and normalized_sku_category == "real_human_model":
        mask_ready_source_path = ensure_mask_compatible_edit_image(source_path, temp_root)
        mask_path = generate_background_mask(mask_ready_source_path, temp_root)
        with Image.open(mask_ready_source_path) as image:
            width, height = image.size
        return PreparedSceneEditImage(
            path=mask_ready_source_path,
            background_removed=False,
            canvas_padded=False,
            anchor="background_mask_lock_subject",
            canvas_size=(width, height),
            subject_bbox=(0, 0, width, height),
            scale_ratio=1.0,
            mask_path=mask_path,
            mask_generated=True,
        )

    if _should_bypass_background_removal_for_subject(normalized_sku_category, subject_type):
        transparent_path = source_path
    else:
        transparent_path = ensure_transparent_background(source_path, temp_root)
    background_removed = transparent_path != source_path

    prepared = _compose_subject_on_canvas(
        transparent_path,
        temp_root,
        sku_category=sku_category,
        subject_type=subject_type,
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
        mask_path=None,
        mask_generated=False,
    )
