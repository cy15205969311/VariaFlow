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
    "apparel_invisible_mannequin": [
        "luxury fashion studio with seamless backdrop, soft editorial key light, and controlled negative space",
        "premium boutique campaign setup with muted wall tones and refined vertical shadow falloff",
        "clean commercial mannequin bay with elegant diffused daylight and high-end catalog styling",
    ],
    "shoes_resting": [
        "sleek fashion plinth with directional studio light and premium texture separation",
        "refined lifestyle floor setup with subtle shadows and modern retail atmosphere",
        "matte editorial surface with crisp contrast and luxury sneaker campaign mood",
    ],
    "bag_standing": [
        "luxury retail display surface with soft directional light and premium material contrast",
        "minimal stone pedestal with elegant boutique atmosphere and refined reflections",
        "editorial fashion tabletop scene with tasteful props and polished highlight control",
    ],
    "accessories_flat": [
        "refined editorial tabletop with subtle texture and airy negative space",
        "minimal fashion flat lay surface with soft window light and premium styling rhythm",
        "clean neutral backdrop with elegant geometric spacing and understated luxury shadows",
    ],
    "beauty_bottle_standing": [
        "premium stone pedestal in a bright skincare studio with crisp highlights",
        "soft neutral vanity scene with airy daylight and refined reflections",
        "minimal acrylic podium with a luminous gradient backdrop and luxury beauty lighting",
    ],
    "beauty_tube_flat": [
        "clean beauty editorial surface with soft daylight and subtle reflections",
        "matte pastel vanity scene with airy premium lighting and delicate beauty props",
        "minimal skincare tabletop with luminous soft shadows and polished ecommerce styling",
    ],
    "beauty_palette_open": [
        "macro beauty tabletop with premium acrylic accents and crisp directional lighting",
        "soft feminine vanity composition with refined shadows and luxe cosmetic styling",
        "high-end makeup campaign surface with editorial close-up lighting and elegant color balance",
    ],
    "jewelry_macro_display": [
        "luxury jewelry plinth with dramatic sparkle lighting and premium reflective highlights",
        "soft velvet display scene with intimate macro lighting and elegant shadow depth",
        "minimal acrylic showcase with concentrated luxury spotlighting and refined reflections",
    ],
    "watch_stand_display": [
        "premium watch boutique display with clean directional light and luxury contrast",
        "dark refined surface with crisp specular highlights and elegant horology campaign styling",
        "architectural studio set with balanced luxury shadows and polished metallic reflections",
    ],
    "electronic_flat": [
        "sleek graphite desk scene with soft tech lighting and premium reflection control",
        "minimal futuristic surface with cool-toned light, clean geometry, and crisp edges",
        "modern productivity tabletop with subtle depth, polished styling, and premium tech atmosphere",
    ],
    "appliance_standing": [
        "clean kitchen-inspired studio environment with balanced daylight and grounded realism",
        "premium showroom floor with controlled reflections and elegant appliance hero lighting",
        "minimal architectural set with soft ambient light and realistic material integration",
    ],
    "furniture_room_setup": [
        "well-designed interior room with natural daylight, floor context, and premium lifestyle styling",
        "editorial home campaign space with layered ambient light and realistic architectural depth",
        "minimal luxury room setup with balanced perspective, decor accents, and polished atmosphere",
    ],
    "home_decor_resting": [
        "tasteful lifestyle tabletop with warm daylight and refined home styling details",
        "editorial interior vignette with subtle decor blur and premium surface textures",
        "soft neutral living-space composition with airy commercial lighting and elegant mood",
    ],
    "food_packaged_standing": [
        "fresh commercial kitchen surface with clean daylight and premium package styling",
        "ingredient-led retail tabletop with appetizing color contrast and grounded shadows",
        "modern grocery campaign setup with natural texture cues and crisp product lighting",
    ],
    "food_plated": [
        "warm dining tabletop with appetizing natural light and rich texture depth",
        "editorial food styling surface with premium props and soft culinary shadows",
        "clean gourmet setup with balanced overhead light and fresh lifestyle composition",
    ],
    "toy_standing": [
        "playful pastel display stage with soft ambient lighting and collectible showcase mood",
        "clean lifestyle shelf scene with warm daylight and subtle decor blur",
        "minimal studio plinth with a colored gradient wash and friendly premium lighting",
    ],
    "plush_sitting": [
        "soft cozy textile surface with warm light and cute lifestyle decor accents",
        "airy pastel room vignette with gentle shadows and plush-friendly premium styling",
        "clean bed or sofa-inspired surface with soft depth and comforting commercial light",
    ],
    "virtual_ip_character": [
        "premium digital campaign backdrop with stylized gradients and polished studio lighting",
        "clean collectible showcase scene with controlled highlights and friendly brand atmosphere",
        "minimal virtual stage with premium color wash and spacious marketing composition",
    ],
    "real_human_model": [
        "editorial fashion studio with premium softbox lighting and natural body shadow modeling",
        "clean campaign backdrop with balanced daylight simulation and polished lifestyle mood",
        "modern fashion set with spacious composition, refined styling, and realistic portrait lighting",
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
    "french_street_vibe": (
        "Set in a beautiful Parisian street cafe outdoors, natural sunlight, blurred aesthetic city background, chic and elegant lifestyle."
    ),
    "luxury_water_surface": (
        "Placed gracefully on a rippling water surface, caustic light reflections, premium cosmetic presentation, ethereal soft atmosphere."
    ),
    "nature_forest_outdoor": (
        "Surrounded by lush green foliage and natural mossy rocks, dappled forest sunlight, earthy organic vibe."
    ),
    "gourmet_morning_bakery": (
        "Bright, airy natural morning sunlight, warm color temperature, soft bright backlighting to enhance food texture. "
        "Mouth-watering, fresh bakery atmosphere with light pastel tones."
    ),
    "luxury_dark_chocolate": (
        "Moody directional lighting, rich warm tones, elegant dark background, highlighting the glossy texture of the food."
    ),
}

SCENE_RECIPE_FALLBACKS = {
    "apparel_flat": ["old_money_vintage", "cozy_winter_morning", "clean_fit_minimal"],
    "apparel_hanging": ["french_street_vibe", "clean_fit_minimal", "old_money_vintage"],
    "apparel_invisible_mannequin": ["french_street_vibe", "clean_fit_minimal", "old_money_vintage"],
    "shoes_resting": ["french_street_vibe", "clean_fit_minimal", "old_money_vintage"],
    "bag_standing": ["french_street_vibe", "old_money_vintage", "clean_fit_minimal"],
    "accessories_flat": ["old_money_vintage", "soft_girly_lifestyle"],
    "beauty_bottle_standing": ["luxury_water_surface", "natural_skincare_luxury", "clean_fit_minimal"],
    "beauty_tube_flat": ["natural_skincare_luxury", "soft_girly_lifestyle"],
    "beauty_palette_open": ["soft_girly_lifestyle", "clean_fit_minimal"],
    "jewelry_macro_display": ["old_money_vintage", "clean_fit_minimal"],
    "watch_stand_display": ["clean_fit_minimal", "old_money_vintage"],
    "electronic_flat": ["clean_fit_minimal", "old_money_vintage"],
    "appliance_standing": ["clean_fit_minimal", "natural_skincare_luxury"],
    "furniture_room_setup": ["clean_fit_minimal", "cozy_winter_morning"],
    "home_decor_resting": ["cozy_winter_morning", "old_money_vintage"],
    "food_packaged_standing": ["gourmet_morning_bakery", "cozy_winter_morning", "luxury_dark_chocolate"],
    "food_plated": ["gourmet_morning_bakery", "luxury_dark_chocolate", "cozy_winter_morning"],
    "toy_standing": ["soft_girly_lifestyle", "clean_fit_minimal"],
    "plush_sitting": ["soft_girly_lifestyle", "cozy_winter_morning"],
    "virtual_ip_character": ["soft_girly_lifestyle", "clean_fit_minimal"],
    "real_human_model": ["french_street_vibe", "clean_fit_minimal", "old_money_vintage"],
    "bottle_standing": ["luxury_water_surface", "natural_skincare_luxury", "clean_fit_minimal"],
    "box_standing": ["clean_fit_minimal", "old_money_vintage"],
    "3d_toy": ["soft_girly_lifestyle", "clean_fit_minimal"],
    "other_flat": ["clean_fit_minimal", "cozy_winter_morning"],
}

NEGATIVE_SPACE_COMPOSITION_RULE = (
    "CRITICAL COMPOSITION: Offset the main subject slightly and ensure ample clean, uncluttered negative space "
    "(empty background area) on the top or sides, specifically designed for adding e-commerce typography and "
    "marketing text later. Do not crop the item too tightly."
)
