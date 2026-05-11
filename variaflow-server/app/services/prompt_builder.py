from __future__ import annotations

import random
from typing import Any

from app.core.config import settings
from app.core.prompt_lexicon import (
    CAMERA_TERMS,
    ENVIRONMENT_TEMPLATES,
    LIGHTING_TERMS,
    NEGATIVE_SPACE_COMPOSITION_RULE,
    QUALITY_TERMS,
    RENDER_TERMS,
    SCENE_RECIPE_FALLBACKS,
    SCENE_RECIPES,
    SPATIAL_GROUNDING_PROMPTS,
)
from app.models.tasks import BatchPromptConfig, GenerationTask, PromptProfile, PromptVariableOption, SourceTask

DEFAULT_POSITIVE_TEMPLATE = (
    "Product photography. A high-quality image of the provided subject {{variant_directive}}. "
    "CRITICAL: The subject is already provided. {{identity_lock}}. "
    "DO NOT modify, warp, recolor, restyle, crop, or change the subject's shape, texture, silhouette, or brand details. "
    "ONLY generate the background, environment, reflections, and natural shadows that match the scene lighting. "
    "Keep the subject centered, complete, and commercially usable."
)
DEFAULT_NEGATIVE_TEMPLATE = (
    "no subject deformation, no extra limbs, no extra fingers, no blur, no watermark, "
    "no text overlay, no duplicated subject, no cropped product, no subject recolor, no subject replacement"
)
DEFAULT_IDENTITY_TEMPLATE = "Preserve the exact subject identity from the reference image."
DEFAULT_QUALITY_TEMPLATE = (
    "photorealistic, premium ecommerce hero image, realistic lighting, natural contact shadow, "
    "clean product composition, sharp focus, marketplace-ready, high detail"
)
DEFAULT_VARIANT_LIBRARY: dict[str, list[str]] = {
    "action": [
        "on a clean wooden table in a sunlit cozy cafe, shallow depth of field, cinematic lighting",
        "placed on white sand at a tropical beach, clear blue sky, ocean waves in background, bright sunlight",
        "on a dark slate podium with neon cyberpunk city lights in the blurred background, moody and futuristic",
        "in a minimalist studio setup with soft pastel gradient background, elegant shadows, product photography",
    ],
    "outfit": [
        "on a clean wooden table in a sunlit cozy cafe, shallow depth of field, cinematic lighting",
        "placed on white sand at a tropical beach, clear blue sky, ocean waves in background, bright sunlight",
        "on a dark slate podium with neon cyberpunk city lights in the blurred background, moody and futuristic",
        "in a minimalist studio setup with soft pastel gradient background, elegant shadows, product photography",
    ],
    "scene": [
        "on a clean wooden table in a sunlit cozy cafe, shallow depth of field, cinematic lighting",
        "placed on white sand at a tropical beach, clear blue sky, ocean waves in background, bright sunlight",
        "on a dark slate podium with neon cyberpunk city lights in the blurred background, moody and futuristic",
        "in a minimalist studio setup with soft pastel gradient background, elegant shadows, product photography",
    ],
    "camera": [
        "front-facing centered product framing",
        "clean commercial hero shot",
        "balanced composition with natural perspective",
    ],
    "style": [
        "high-end ecommerce background integration",
        "premium marketplace-ready product presentation",
        "realistic environmental background blending",
    ],
}

POSE_VARIATION_ACTION_LIBRARY = [
    "wave one hand naturally while wearing a sleek cyberpunk bomber jacket",
    "jump lightly with an energetic expression while wearing a soft pastel hoodie",
    "hold a takeaway coffee cup with a relaxed smile while wearing a tailored modern suit",
    "stand confidently with one hand on the hip while wearing a sporty varsity jacket",
    "lean forward in a playful commercial pose while wearing a trendy streetwear windbreaker",
]


def _build_magic_enhancers() -> str:
    enhancer_terms = [
        *QUALITY_TERMS,
        *LIGHTING_TERMS,
        *CAMERA_TERMS,
        *RENDER_TERMS,
    ]
    return ", ".join(term for term in enhancer_terms if str(term).strip())


def _normalize_scene_text(raw: str | None) -> str:
    return " ".join(str(raw or "").split()).strip()


def _normalize_scene_recipe_key(raw: str | None) -> str:
    value = _normalize_scene_text(raw).lower()
    return value if value in SCENE_RECIPES else ""


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
        return f"in the following background scene: {fragments['action_fragment']}"
    if axis == "outfit":
        return f"in the following background scene: {fragments['outfit_fragment']}"
    if axis == "scene":
        return f"in the following background scene: {fragments['scene_fragment']}"

    scene_fragments: list[str] = []
    for key in ("scene_fragment", "action_fragment", "outfit_fragment"):
        value = fragments.get(key, "").strip()
        if value and value not in scene_fragments:
            scene_fragments.append(value)

    if not scene_fragments:
        return "in a realistic ecommerce-ready background scene"
    return f"in the following background scene: {scene_fragments[0]}"


def _build_pose_variation_prompt(
    *,
    identity_lock: str,
    fragments: dict[str, str],
    quality_template: str,
    subject_features: str | None = None,
    style_features: str | None = None,
    background_features: str | None = None,
) -> str:
    slot_seed = (
        sum(ord(char) for char in (subject_features or ""))
        + len(style_features or "")
        + len(background_features or "")
        + len(identity_lock or "")
    )
    fallback_action = POSE_VARIATION_ACTION_LIBRARY[slot_seed % len(POSE_VARIATION_ACTION_LIBRARY)]
    action_required = fallback_action
    scene_inspiration = (
        fragments.get("scene_fragment")
        or fragments.get("action_fragment")
        or fragments.get("outfit_fragment")
        or ""
    ).strip()
    style_clause = style_features.strip() if style_features and style_features.strip() else (
        "premium stylized 3D character render with polished materials, appealing cinematic lighting, and refined toy-like detailing"
    )
    background_clause = background_features.strip() if background_features and background_features.strip() else (
        scene_inspiration or "a premium commercial lifestyle background with depth and atmosphere"
    )
    subject_clause = subject_features.strip() if subject_features and subject_features.strip() else (
        "the exact same character identity, species, facial features, body proportions, and signature visual traits"
    )
    camera_clause = fragments.get("camera_fragment", "").strip()
    quality_clause = quality_template.strip()
    style_tail = ", ".join(
        part
        for part in [camera_clause, fragments.get("style_fragment", "").strip(), quality_clause]
        if part
    )
    enhancers = _build_magic_enhancers()
    return (
        "Create a masterpiece, ultra-high definition image of the exact same IP character in a new pose. "
        f"Must strictly adhere to this exact artistic style and lighting: [{style_clause}]. "
        f"The environment and background must be: [{background_clause}]. "
        f"The main character must exactly match this physical description and identity, without changing species, face, body proportions, or signature traits: [{subject_clause}]. "
        f"{identity_lock}. "
        "Preserve the same premium 3D blind-box quality, facial appeal, material richness, and overall charm. "
        "Do not create a different character. Do not drift into a generic monkey. "
        f"ACTION & OUTFIT MODIFICATION: The character is now doing the following action and wearing this outfit: {action_required}. "
        f"Ensure the result feels like the exact same IP in a new pose. "
        f"COMMERCIAL PHOTOGRAPHY REQUIREMENTS: {enhancers}. "
        f"{style_tail}"
    ).strip()


def _build_scene_edit_prompt(
    *,
    positive_template: str,
    identity_lock: str,
    scene_variant_directive: str,
    fragments: dict[str, str],
    quality_template: str,
    sku_category: str,
    scene_recipe_key: str,
    scene_environment: str,
) -> str:
    grounding_prompt = SPATIAL_GROUNDING_PROMPTS.get(
        sku_category,
        SPATIAL_GROUNDING_PROMPTS["other_flat"],
    )
    base_prompt = (
        positive_template
        .replace("{{identity_lock}}", identity_lock)
        .replace("{{variant_directive}}", scene_variant_directive)
    )
    return ", ".join(
        fragment
        for fragment in [
            f"CRITICAL GROUNDING: {grounding_prompt}.",
            f"VIRAL SCENE RECIPE: {scene_recipe_key}.",
            f"ENVIRONMENT & BACKGROUND: {scene_environment}.",
            "Ensure realistic drop shadows, believable surface contact, and seamless commercial integration.",
            NEGATIVE_SPACE_COMPOSITION_RULE,
            base_prompt,
            fragments["camera_fragment"],
            fragments["style_fragment"],
            quality_template,
        ]
        if fragment
    )


def _build_real_human_pose_edit_prompt(
    *,
    identity_lock: str,
    fragments: dict[str, str],
    quality_template: str,
    subject_features: str | None = None,
    style_features: str | None = None,
    background_features: str | None = None,
) -> str:
    style_clause = style_features.strip() if style_features and style_features.strip() else (
        "premium editorial fashion photography with realistic human skin tones, elegant lighting, and natural body volume"
    )
    background_clause = background_features.strip() if background_features and background_features.strip() else (
        fragments.get("scene_fragment", "").strip() or "a premium commercial lifestyle background"
    )
    subject_clause = subject_features.strip() if subject_features and subject_features.strip() else (
        "the exact same real human model identity, facial features, body proportions, and styling essence"
    )
    camera_clause = fragments.get("camera_fragment", "").strip()
    style_tail = ", ".join(
        part
        for part in [camera_clause, fragments.get("style_fragment", "").strip(), quality_template.strip()]
        if part
    )
    return (
        "Use the provided real human model image as the direct visual reference. "
        f"Preserve the exact same person identity and recognizability: [{subject_clause}]. "
        f"Maintain this premium photography style and lighting language: [{style_clause}]. "
        f"Keep the scene atmosphere aligned with: [{background_clause}]. "
        f"{identity_lock}. "
        "Generate a tasteful pose or styling variation of the same real person while preserving facial identity, body continuity, garment integrity, and realistic grounding. "
        "Do not replace the person with a different model or mannequin. Do not crop off the head, hands, or feet. "
        f"{style_tail}"
    ).strip()


def _resolve_scene_environment(
    *,
    suggested_scene: str | None,
    sku_category: str,
    source_task: SourceTask,
    generation_task: GenerationTask,
) -> tuple[str, str]:
    normalized_recipe_key = _normalize_scene_recipe_key(suggested_scene)
    if normalized_recipe_key:
        return normalized_recipe_key, SCENE_RECIPES[normalized_recipe_key]

    recipe_options = SCENE_RECIPE_FALLBACKS.get(
        sku_category,
        SCENE_RECIPE_FALLBACKS["other_flat"],
    )
    seed_value = generation_task.variant_index + sum(ord(char) for char in (source_task.source_hash or ""))
    fallback_recipe_key = recipe_options[seed_value % len(recipe_options)]
    return fallback_recipe_key, SCENE_RECIPES[fallback_recipe_key]


def _resolve_scene_supporting_environment(
    *,
    sku_category: str,
    source_task: SourceTask,
    generation_task: GenerationTask,
) -> str:
    options = ENVIRONMENT_TEMPLATES.get(
        sku_category,
        ENVIRONMENT_TEMPLATES["other_flat"],
    )
    seed_value = generation_task.variant_index + sum(ord(char) for char in (source_task.source_hash or ""))
    return options[seed_value % len(options)]


def build_provider_payload(
    source_task: SourceTask,
    generation_task: GenerationTask,
    prompt_profile: PromptProfile | None = None,
    batch_config: BatchPromptConfig | None = None,
    intent: str = "SCENE_EDIT",
    intent_reason: str | None = None,
    subject_features: str | None = None,
    style_features: str | None = None,
    background_features: str | None = None,
    sku_category: str | None = None,
    suggested_scene: str | None = None,
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

    normalized_intent = str(intent or "SCENE_EDIT").strip().upper()
    normalized_sku_category = str(sku_category or "other_flat").strip().lower() or "other_flat"
    resolved_scene_recipe_key, resolved_scene_recipe = _resolve_scene_environment(
        suggested_scene=suggested_scene,
        sku_category=normalized_sku_category,
        source_task=source_task,
        generation_task=generation_task,
    )
    resolved_supporting_environment = _resolve_scene_supporting_environment(
        sku_category=normalized_sku_category,
        source_task=source_task,
        generation_task=generation_task,
    )
    resolved_scene_environment = (
        f"{resolved_scene_recipe} Supporting surface and lighting continuity: {resolved_supporting_environment}"
    )
    scene_variant_directive = f"in the following background environment: {resolved_scene_environment}"
    if normalized_intent == "POSE_VARIATION" and normalized_sku_category == "real_human_model":
        final_prompt = _build_real_human_pose_edit_prompt(
            identity_lock=identity_lock,
            fragments=fragments,
            quality_template=quality_template,
            subject_features=subject_features,
            style_features=style_features,
            background_features=background_features,
        )
    elif normalized_intent == "POSE_VARIATION":
        final_prompt = _build_pose_variation_prompt(
            identity_lock=identity_lock,
            fragments=fragments,
            quality_template=quality_template,
            subject_features=subject_features,
            style_features=style_features,
            background_features=background_features,
        )
    else:
        final_prompt = _build_scene_edit_prompt(
            positive_template=positive_template,
            identity_lock=identity_lock,
            scene_variant_directive=scene_variant_directive,
            fragments=fragments,
            quality_template=quality_template,
            sku_category=normalized_sku_category,
            scene_recipe_key=resolved_scene_recipe_key,
            scene_environment=resolved_scene_environment,
        )

    prompt_snapshot = {
        "intent": normalized_intent,
        "intent_reason": intent_reason,
        "sku_category": normalized_sku_category,
        "suggested_scene": resolved_scene_recipe_key if normalized_intent == "SCENE_EDIT" else "",
        "suggested_scene_prompt": resolved_scene_environment if normalized_intent == "SCENE_EDIT" else "",
        "subject_features": subject_features if normalized_intent == "POSE_VARIATION" else "",
        "style_features": style_features if normalized_intent == "POSE_VARIATION" else "",
        "background_features": background_features if normalized_intent == "POSE_VARIATION" else "",
        "identity_lock": identity_lock,
        "positive_template": positive_template,
        "negative_template": negative_template,
        "quality_template": quality_template,
        "variant_axis": axis,
        "variant_directive": scene_variant_directive if normalized_intent == "SCENE_EDIT" else variant_directive,
        **fragments,
    }

    provider_payload = {
        "prompt": final_prompt,
        "size": "1024x1024",
        "source_image_name": source_task.source_name or f"source.{source_task.source_ext or 'png'}",
        "source_image_path": source_task.source_path,
        "openai_model": settings.openai_image_model,
        "aliyun_model": settings.aliyun_wanx_model,
        "intent": normalized_intent,
        "sku_category": normalized_sku_category,
        "suggested_scene": resolved_scene_recipe_key if normalized_intent == "SCENE_EDIT" else "",
        "suggested_scene_prompt": resolved_scene_environment if normalized_intent == "SCENE_EDIT" else "",
        "subject_features": subject_features if normalized_intent == "POSE_VARIATION" else "",
        "style_features": style_features if normalized_intent == "POSE_VARIATION" else "",
        "background_features": background_features if normalized_intent == "POSE_VARIATION" else "",
        "provider_hint": (
            "openai_image_edit"
            if normalized_intent == "POSE_VARIATION" and normalized_sku_category == "real_human_model"
            else "openai_image_generation"
            if normalized_intent == "POSE_VARIATION"
            else "openai_image_edit"
        ),
    }

    if negative_template:
        provider_payload["prompt"] = (
            f"{provider_payload['prompt']}\n\nNegative prompt: {negative_template}"
        )

    prompt_snapshot["provider_context"] = {
        "batch_code": source_task.batch.batch_code if source_task.batch else None,
        "source_task_id": source_task.id,
        "generation_task_id": generation_task.id,
        "original_source_image_path": source_task.source_path,
        "source_hash": source_task.source_hash,
        "variant_index": generation_task.variant_index,
        "variant_axis": axis,
        "random_seed": random.randint(1000, 999999),
    }

    return provider_payload, prompt_snapshot
