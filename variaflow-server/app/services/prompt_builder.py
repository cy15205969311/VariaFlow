from __future__ import annotations

import random
from typing import Any

from app.models.tasks import BatchPromptConfig, GenerationTask, PromptProfile, PromptVariableOption, SourceTask

DEFAULT_POSITIVE_TEMPLATE = (
    "Keep the subject identity consistent with the reference image. "
    "{{identity_lock}}. Apply the requested variation: {{variant_directive}}."
)
DEFAULT_NEGATIVE_TEMPLATE = (
    "no extra limbs, no extra fingers, no blur, no watermark, "
    "no text overlay, no duplicated subject, no cropped product"
)
DEFAULT_IDENTITY_TEMPLATE = "Preserve the exact subject identity from the reference image."
DEFAULT_QUALITY_TEMPLATE = (
    "high detail, clean commercial composition, complete subject, "
    "sharp focus, marketplace-ready hero image"
)
DEFAULT_VARIANT_LIBRARY: dict[str, list[str]] = {
    "action": [
        "raise one hand in a friendly pose",
        "stand with a slight turn and confident posture",
        "lean forward in a lively commercial pose",
    ],
    "outfit": [
        "wear a casual streetwear outfit",
        "wear a sporty coordinated outfit",
        "wear a clean premium retail outfit",
    ],
    "scene": [
        "place the subject in a bright lifestyle studio scene",
        "place the subject in a playful retail display scene",
        "place the subject in a clean seasonal campaign backdrop",
    ],
    "camera": [
        "front-facing hero shot",
        "slight three-quarter angle",
        "medium close-up commercial framing",
    ],
    "style": [
        "high-end ecommerce hero image",
        "clean marketplace product visual",
        "premium catalog presentation",
    ],
}


def _choose_slot_value(values: list[str], slot_seed: int) -> str:
    if not values:
        return ""
    return values[(slot_seed - 1) % len(values)]


def _normalize_option_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    if isinstance(raw, dict):
        return [str(value).strip() for value in raw.values() if str(value).strip()]
    return [str(raw).strip()]


def _options_from_profile(variable_options: list[PromptVariableOption], variable_type: str) -> list[str]:
    return [
        option.prompt_fragment
        for option in sorted(variable_options, key=lambda item: item.sort_order)
        if option.variable_type == variable_type and option.is_enabled
    ]


def _pick_variants(
    *,
    generation_task: GenerationTask,
    prompt_profile: PromptProfile | None,
    batch_config: BatchPromptConfig | None,
) -> dict[str, str]:
    variable_options = prompt_profile.variable_options if prompt_profile else []
    slot_seed = generation_task.variant_index

    selected_actions = (
        _normalize_option_list(batch_config.selected_actions_json if batch_config else None)
        or _options_from_profile(variable_options, "action")
        or DEFAULT_VARIANT_LIBRARY["action"]
    )
    selected_outfits = (
        _normalize_option_list(batch_config.selected_outfits_json if batch_config else None)
        or _options_from_profile(variable_options, "outfit")
        or DEFAULT_VARIANT_LIBRARY["outfit"]
    )
    selected_scenes = (
        _normalize_option_list(batch_config.selected_scenes_json if batch_config else None)
        or _options_from_profile(variable_options, "scene")
        or DEFAULT_VARIANT_LIBRARY["scene"]
    )
    selected_cameras = (
        _normalize_option_list(batch_config.selected_cameras_json if batch_config else None)
        or _options_from_profile(variable_options, "camera")
        or DEFAULT_VARIANT_LIBRARY["camera"]
    )
    selected_styles = (
        _normalize_option_list(batch_config.selected_styles_json if batch_config else None)
        or _options_from_profile(variable_options, "style")
        or DEFAULT_VARIANT_LIBRARY["style"]
    )

    return {
        "action_fragment": _choose_slot_value(selected_actions, slot_seed),
        "outfit_fragment": _choose_slot_value(selected_outfits, slot_seed),
        "scene_fragment": _choose_slot_value(selected_scenes, slot_seed),
        "camera_fragment": _choose_slot_value(selected_cameras, slot_seed),
        "style_fragment": _choose_slot_value(selected_styles, slot_seed),
    }


def _build_variant_directive(axis: str, fragments: dict[str, str]) -> str:
    if axis == "action":
        return fragments["action_fragment"]
    if axis == "outfit":
        return fragments["outfit_fragment"]
    if axis == "scene":
        return fragments["scene_fragment"]
    return ", ".join(
        fragment
        for fragment in [
            fragments["action_fragment"],
            fragments["outfit_fragment"],
            fragments["scene_fragment"],
        ]
        if fragment
    )


def build_provider_payload(
    source_task: SourceTask,
    generation_task: GenerationTask,
    prompt_profile: PromptProfile | None = None,
    batch_config: BatchPromptConfig | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    组装发往模型网关的标准化载荷，并同时返回一份可落库审计的快照。

    当前实现兼容两种调用方式：
    - 仅传入 `source_task` 与 `generation_task`，使用默认模板；
    - 额外传入 `prompt_profile` / `batch_config`，使用数据库配置。
    """

    identity_profile = source_task.identity_profile_json or {}
    axis = generation_task.variant_axis.value
    fragments = _pick_variants(
        generation_task=generation_task,
        prompt_profile=prompt_profile,
        batch_config=batch_config,
    )
    variant_directive = _build_variant_directive(axis, fragments)

    positive_template = (
        batch_config.positive_override
        if batch_config and batch_config.positive_override
        else (prompt_profile.positive_template if prompt_profile else DEFAULT_POSITIVE_TEMPLATE)
    )
    negative_template = (
        batch_config.negative_override
        if batch_config and batch_config.negative_override
        else (prompt_profile.negative_template if prompt_profile else DEFAULT_NEGATIVE_TEMPLATE)
    )
    quality_template = (
        batch_config.quality_override
        if batch_config and batch_config.quality_override
        else (
            prompt_profile.quality_template
            if prompt_profile and prompt_profile.quality_template
            else DEFAULT_QUALITY_TEMPLATE
        )
    )
    identity_lock = (
        batch_config.identity_lock_override
        if batch_config and batch_config.identity_lock_override
        else identity_profile.get("identity_lock")
        or (
            prompt_profile.identity_template
            if prompt_profile and prompt_profile.identity_template
            else DEFAULT_IDENTITY_TEMPLATE
        )
    )

    final_prompt = (
        positive_template
        .replace("{{identity_lock}}", identity_lock)
        .replace("{{variant_directive}}", variant_directive)
    )
    final_prompt = ", ".join(
        fragment
        for fragment in [
            final_prompt,
            fragments["camera_fragment"],
            fragments["style_fragment"],
            quality_template,
        ]
        if fragment
    )

    prompt_snapshot = {
        "identity_lock": identity_lock,
        "positive_template": positive_template,
        "negative_template": negative_template,
        "quality_template": quality_template,
        "variant_axis": axis,
        "variant_directive": variant_directive,
        **fragments,
    }

    provider_payload = {
        "model": "image-2",
        "prompt": final_prompt,
        "negative_prompt": negative_template,
        "reference_image_path": source_task.source_path,
        "batch_code": source_task.batch.batch_code if source_task.batch else None,
        "source_task_id": source_task.id,
        "generation_task_id": generation_task.id,
        "size": "1024x1024",
        "metadata": {
            "source_hash": source_task.source_hash,
            "variant_index": generation_task.variant_index,
            "variant_axis": axis,
            "random_seed": random.randint(1000, 999999),
        },
    }

    return provider_payload, prompt_snapshot
