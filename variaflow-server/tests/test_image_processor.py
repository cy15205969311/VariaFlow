from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

from app.utils.image_processor import ensure_transparent_background, prepare_scene_edit_source_image


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


def test_prepare_scene_edit_source_image_pads_flat_apparel_into_bottom_center_layout(tmp_path: Path) -> None:
    source_path = tmp_path / "flat_apparel.png"
    canvas = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    subject = Image.new("RGBA", (320, 260), (240, 240, 240, 255))
    canvas.paste(subject, (96, 120), subject)
    canvas.save(source_path, format="PNG")

    prepared = prepare_scene_edit_source_image(
        source_path,
        tmp_path / "preprocessed",
        sku_category="apparel_flat",
        subject_type="product_only",
        suggested_scene="cozy_winter_morning",
        target_size="1024x1024",
    )

    assert prepared.path.exists()
    assert prepared.background_removed is False
    assert prepared.canvas_padded is True
    assert prepared.canvas_size == (1024, 1024)
    assert prepared.anchor == "bottom_center"
    left, top, right, bottom = prepared.subject_bbox
    assert right - left < 760
    assert bottom > 700
    assert top > 350

    with Image.open(prepared.path) as result_image:
        assert result_image.size == (1024, 1024)
        alpha_bbox = result_image.getchannel("A").getbbox()
        assert alpha_bbox == prepared.subject_bbox


def test_prepare_scene_edit_source_image_uses_scene_override_for_minimal_recipe(tmp_path: Path) -> None:
    source_path = tmp_path / "box.png"
    canvas = Image.new("RGBA", (400, 400), (0, 0, 0, 0))
    subject = Image.new("RGBA", (220, 220), (60, 60, 60, 255))
    canvas.paste(subject, (90, 90), subject)
    canvas.save(source_path, format="PNG")

    prepared = prepare_scene_edit_source_image(
        source_path,
        tmp_path / "preprocessed",
        sku_category="box_standing",
        subject_type="product_only",
        suggested_scene="clean_fit_minimal",
        target_size="1024x1024",
    )

    left, top, right, bottom = prepared.subject_bbox
    assert prepared.anchor == "bottom_center"
    assert left > 180
    assert right < 844
    assert bottom > 700


def test_prepare_scene_edit_source_image_supports_expanded_human_model_layout(tmp_path: Path) -> None:
    source_path = tmp_path / "human_model.png"
    canvas = Image.new("RGBA", (420, 900), (0, 0, 0, 0))
    subject = Image.new("RGBA", (260, 760), (180, 180, 180, 255))
    canvas.paste(subject, (80, 80), subject)
    canvas.save(source_path, format="PNG")

    prepared = prepare_scene_edit_source_image(
        source_path,
        tmp_path / "preprocessed",
        sku_category="real_human_model",
        subject_type="human_model",
        suggested_scene="clean_fit_minimal",
        target_size="1024x1024",
    )

    left, top, right, bottom = prepared.subject_bbox
    assert prepared.anchor == "bottom_center"
    assert bottom > 700
    assert top > 120
    assert right - left < 640


def test_prepare_scene_edit_source_image_bypasses_rembg_for_real_human_model(tmp_path: Path) -> None:
    source_path = tmp_path / "human_model_photo.jpg"
    image = Image.new("RGB", (320, 640), (180, 170, 160))
    image.save(source_path, format="JPEG")

    prepared = prepare_scene_edit_source_image(
        source_path,
        tmp_path / "preprocessed",
        sku_category="real_human_model",
        subject_type="human_model",
        suggested_scene="french_street_vibe",
        target_size="1024x1024",
    )

    assert prepared.background_removed is False
    assert prepared.canvas_padded is True
    assert prepared.anchor == "bottom_center"


def test_prepare_scene_edit_source_image_top_aligns_hanging_apparel(tmp_path: Path) -> None:
    source_path = tmp_path / "hanging_apparel.png"
    canvas = Image.new("RGBA", (400, 800), (0, 0, 0, 0))
    subject = Image.new("RGBA", (220, 620), (120, 120, 120, 255))
    canvas.paste(subject, (90, 90), subject)
    canvas.save(source_path, format="PNG")

    prepared = prepare_scene_edit_source_image(
        source_path,
        tmp_path / "preprocessed",
        sku_category="apparel_hanging",
        subject_type="product_only",
        suggested_scene="french_street_vibe",
        target_size="1024x1024",
    )

    left, top, right, bottom = prepared.subject_bbox
    assert prepared.anchor == "top_center"
    assert top < 120
    assert bottom < 900


def test_prepare_scene_edit_source_image_bypasses_rembg_for_human_subject_type_even_without_human_sku(tmp_path: Path) -> None:
    source_path = tmp_path / "editorial_model.jpg"
    image = Image.new("RGB", (360, 720), (200, 180, 170))
    image.save(source_path, format="JPEG")

    prepared = prepare_scene_edit_source_image(
        source_path,
        tmp_path / "preprocessed",
        sku_category="other_flat",
        subject_type="human_model",
        suggested_scene="french_street_vibe",
        target_size="1024x1024",
    )

    assert prepared.background_removed is False
    assert prepared.canvas_padded is True
