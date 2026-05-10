from __future__ import annotations

QUALITY_TERMS = [
    "masterpiece",
    "best quality",
    "ultra-detailed",
    "8k resolution",
    "photorealistic",
    "RAW photo quality",
]

LIGHTING_TERMS = [
    "soft studio lighting",
    "cinematic lighting",
    "volumetric light",
    "rim light",
    "highly detailed shadows",
]

CAMERA_TERMS = [
    "shot on 85mm lens",
    "f/1.8 aperture",
    "shallow depth of field",
    "elegant minimalist composition",
    "negative space",
]

RENDER_TERMS = [
    "Octane render",
    "Unreal Engine 5 look",
    "ray tracing",
    "subsurface scattering",
    "matte vinyl toy texture",
    "high-end blind box toy material",
]

SPATIAL_GROUNDING_PROMPTS = {
    "apparel_flat": "professional flat lay photography, laid naturally with realistic fabric folds, top-down view",
    "apparel_hanging": "hanging naturally with realistic vertical fabric drape, photographed straight-on",
    "bottle_standing": "standing upright with a stable base contact and realistic contact shadow directly beneath the product",
    "box_standing": "placed solidly with realistic perspective and grounded edge shadows",
    "3d_toy": "standing securely with realistic occlusion shadow beneath the feet or base",
    "other_flat": "placed naturally in a grounded resting position with soft drop shadows",
}

ENVIRONMENT_TEMPLATES = {
    "apparel_flat": [
        "soft ivory editorial backdrop with diffused daylight and subtle textile styling",
        "refined beige linen surface with gentle window light and spacious negative space",
        "matte pastel studio paper setup with clean commercial lighting and elegant soft shadows",
    ],
    "apparel_hanging": [
        "minimalist concrete wall with soft natural window light",
        "warm boutique fitting room scene with elegant shadow falloff",
        "clean gallery-style wall with a premium rack and diffused studio lighting",
    ],
    "bottle_standing": [
        "premium stone pedestal in a bright skincare studio with crisp highlights",
        "soft neutral vanity scene with airy daylight and refined reflections",
        "minimal acrylic podium with a luminous gradient backdrop and luxury beauty lighting",
    ],
    "box_standing": [
        "clean neutral studio backdrop with subtle depth and premium catalog lighting",
        "sleek retail display scene with soft side light and crisp contrast",
        "matte architectural pedestal environment with elegant shadows and restrained reflections",
    ],
    "3d_toy": [
        "playful pastel display stage with soft ambient lighting and collectible showcase mood",
        "clean lifestyle shelf scene with warm daylight and subtle decor blur",
        "minimal studio plinth with a colored gradient wash and friendly premium lighting",
    ],
    "other_flat": [
        "clean editorial tabletop scene with soft daylight and understated texture",
        "minimal seamless studio backdrop with gentle shadow layering",
        "soft neutral surface with airy commercial lighting and polished negative space",
    ],
}

SCENE_RECIPES = {
    "old_money_vintage": (
        "Dark rich wood surface, subtle dappled sunlight from a window blind, accompanied by aesthetic props like "
        "an open vintage book, a cup of black coffee, and brass accessories. Moody cinematic color grading, deep shadows."
    ),
    "clean_fit_minimal": (
        "Matte concrete or sleek white marble surface, harsh minimalist studio flash lighting, sparse geometric props "
        "like a sleek silver watch or modern sunglasses. High contrast, desaturated cool tones."
    ),
    "cozy_winter_morning": (
        "Placed on a fluffy white wool blanket, warm golden hour morning light, soft bokeh, props include a steaming mug "
        "and dried autumn leaves. Warm, soft, comforting atmosphere."
    ),
    "soft_girly_lifestyle": (
        "Soft blush or cream surface with airy daylight, delicate props like ribbons, perfume bottles, or a compact mirror. "
        "Clean feminine styling, gentle highlights, dreamy premium ecommerce mood."
    ),
    "natural_skincare_luxury": (
        "Clean stone or travertine display surface with luminous daylight, subtle water reflections, and premium beauty props "
        "such as folded towels, glass droppers, or botanical accents. Refined luxury skincare campaign mood."
    ),
}

SCENE_RECIPE_FALLBACKS = {
    "apparel_flat": ["old_money_vintage", "cozy_winter_morning", "clean_fit_minimal"],
    "apparel_hanging": ["clean_fit_minimal", "old_money_vintage"],
    "bottle_standing": ["natural_skincare_luxury", "clean_fit_minimal"],
    "box_standing": ["clean_fit_minimal", "old_money_vintage"],
    "3d_toy": ["soft_girly_lifestyle", "clean_fit_minimal"],
    "other_flat": ["clean_fit_minimal", "cozy_winter_morning"],
}

NEGATIVE_SPACE_COMPOSITION_RULE = (
    "CRITICAL COMPOSITION: Offset the main subject slightly and ensure ample clean, uncluttered negative space "
    "(empty background area) on the top or sides, specifically designed for adding e-commerce typography and "
    "marketing text later. Do not crop the item too tightly."
)
