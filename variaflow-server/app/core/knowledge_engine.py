from __future__ import annotations

from dataclasses import dataclass

DEFAULT_PHYSICAL_CONSTRAINT = (
    "Keep the subject physically believable in the environment with realistic weight, gravity, "
    "and contact shadow behavior."
)

DEFAULT_CAMERA_PERSPECTIVE = "eye-level"

DEFAULT_PROP_RULES = {
    "allow_props": True,
    "banned_terms": {"watch"},
}

SUPPORTED_MATERIAL_TYPES = (
    "fabric_soft",
    "fabric_stiff",
    "reflective_glass",
    "leather_or_pu",
    "matte_solid",
)

MATERIAL_LIGHTING_RULES = {
    "fabric_soft": "Soft diffused lighting to highlight textile weave, visible knit depth, natural fabric folds, and gentle shadow transitions, avoiding harsh shadows.",
    "fabric_stiff": "Directional studio light to emphasize structured silhouette and tailoring.",
    "reflective_glass": "Sharp caustic light reflections, backlighting to emphasize transparency and liquid textures, plus crisp mirror reflections and controlled highlight strips.",
    "leather_or_pu": "Subtle specular highlights to showcase leather grain and premium material finish.",
    "matte_solid": "Controlled commercial lighting with clean edge separation, realistic volume, and balanced surface detail.",
}

INVALID_CATEGORY_POSES = {
    "apparel_flat": ("leaning", "standing_upright"),
    "apparel_hanging": ("leaning", "laying_flat"),
    "plush_sitting": ("leaning_against_wall",),
}

CATEGORY_POSE_ALIASES = {
    "apparel_flat": "laying_flat",
    "apparel_hanging": "hanging",
    "apparel_leaning": "leaning",
    "apparel_invisible_mannequin": "standing_upright",
    "plush_sitting": "sitting",
}

SOFT_APPAREL_DESCRIPTION_KEYWORDS = {
    "hoodie",
    "sweater",
    "knit",
    "knitted",
    "cardigan",
    "jumper",
    "sweatshirt",
    "tee",
    "t-shirt",
    "shirt",
    "blouse",
    "dress",
    "skirt",
    "jeans",
    "pants",
    "trousers",
    "coat",
    "jacket",
    "fleece",
    "wool",
    "cashmere",
    "garment",
    "apparel",
    "pullover",
}

GLASS_LIQUID_MATERIAL_KEYWORDS = {
    "glass",
    "serum",
    "perfume",
    "essence",
    "ampoule",
    "liquid",
    "oil",
    "lotion",
    "toner",
    "mist",
    "translucent",
}

STIFF_FABRIC_MATERIAL_KEYWORDS = {
    "blazer",
    "suit",
    "tailored",
    "tailoring",
    "structured",
    "trench",
    "denim jacket",
    "corset",
    "puffer",
    "quilted",
}

LEATHER_PU_MATERIAL_KEYWORDS = {
    "leather",
    "pu leather",
    "faux leather",
    "patent",
    "suede",
    "nubuck",
}

KNIT_FLEECE_MATERIAL_KEYWORDS = {
    "knit",
    "knitted",
    "fleece",
    "wool",
    "cashmere",
    "sweater",
    "hoodie",
    "cardigan",
    "jumper",
    "sweatshirt",
    "soft-touch",
    "soft touch",
    "plush",
    "fuzzy",
}


@dataclass(frozen=True, slots=True)
class DomainConstraint:
    sku_category: str
    recommended_camera_perspective: str
    physics_constraints: str
    prompt_prefix: str = ""
    negative_prompt: str = ""
    perspective_lock: str = ""
    allowed_props: tuple[str, ...] = ()
    banned_props: tuple[str, ...] = ()
    props_required: bool = False
    allow_dynamic_props: bool = True


DOMAIN_CONSTRAINTS: dict[str, DomainConstraint] = {
    "apparel_flat": DomainConstraint(
        sku_category="apparel_flat",
        recommended_camera_perspective="top-down",
        physics_constraints="Must preserve realistic fabric folds, grounded wrinkles, and tight contact shadows directly around the garment edges.",
        allowed_props=("editorial magazine", "ceramic coffee cup", "dried floral accent", "delicate necklace", "perfume bottle"),
    ),
    "apparel_hanging": DomainConstraint(
        sku_category="apparel_hanging",
        recommended_camera_perspective="eye-level",
        physics_constraints="Maintain natural gravity drape, vertical garment fall, and ensure the lower hem does not touch the ground.",
        allowed_props=("minimal wooden hanger", "metal hanger", "soft tree-shadow pattern"),
    ),
    "apparel_leaning": DomainConstraint(
        sku_category="apparel_leaning",
        recommended_camera_perspective="30-to-45-degree angular side view",
        physics_constraints="Must generate a clear 90-degree intersection between a vertical wall and a horizontal floor. The apparel must lean naturally against the wall with realistic gravity and contact shadows.",
        prompt_prefix="A composition featuring a clean 90-degree intersection of a vertical minimalist wall and a horizontal solid floor. The apparel is leaning naturally against the wall.",
        allowed_props=("framed wall art", "green foliage accent", "window-grid light pattern"),
    ),
    "real_human_model": DomainConstraint(
        sku_category="real_human_model",
        recommended_camera_perspective="match the original reference perspective exactly",
        physics_constraints="Preserve full human body continuity, realistic stance, natural limb anatomy, and believable floor contact without amputating or floating body parts.",
        negative_prompt=(
            "ABSOLUTELY DO NOT add any new accessories, jewelry, bags, or props to the human model. "
            "Strictly NO new accessories, NO extra jewelry, NO bags, NO watches, NO hats. "
            "Preserve every pixel of the person and clothing."
        ),
        allow_dynamic_props=False,
    ),
    "shoes_resting": DomainConstraint(
        sku_category="shoes_resting",
        recommended_camera_perspective="low-angle 45-degree side view",
        physics_constraints="The footwear must remain firmly grounded on a believable floor plane with realistic sole contact, pressure shadows at the contact points, correct perspective convergence, and non-distorted structure.",
        perspective_lock=(
            "CRITICAL: Match the camera angle and perspective of the original shoe exactly. "
            "Do NOT distort the shoe's geometry. The floor plane must align perfectly with the shoe's grounding angle. "
            "Ensure the ground plane matches the reference shoe orientation. No geometric warping. "
            "Realistic pressure shadows at the contact points."
        ),
        allowed_props=("minimal stair block", "marble texture surface", "tonal socks"),
    ),
    "bag_standing": DomainConstraint(
        sku_category="bag_standing",
        recommended_camera_perspective="slight 15-degree top-down view",
        physics_constraints="Keep the bag body supported from within, preserve realistic volume, and allow handles to fall naturally with believable gravity.",
        allowed_props=("silk scarf", "lipstick", "sunglasses", "premium serving tray"),
    ),
    "beauty_bottle": DomainConstraint(
        sku_category="beauty_bottle",
        recommended_camera_perspective="eye-level or macro close-up",
        physics_constraints="Preserve clean glass symmetry, transparent highlights, and elegant mirror reflection behavior beneath the bottle.",
        allowed_props=("water splash", "acrylic podium", "ingredient raw materials"),
    ),
    "beauty_bottle_standing": DomainConstraint(
        sku_category="beauty_bottle_standing",
        recommended_camera_perspective="eye-level or macro close-up",
        physics_constraints="Preserve clean glass symmetry, transparent highlights, and elegant mirror reflection behavior beneath the bottle.",
        allowed_props=("water splash", "acrylic podium", "ingredient raw materials"),
    ),
    "food_plated": DomainConstraint(
        sku_category="food_plated",
        recommended_camera_perspective="45-degree top-down dining angle",
        physics_constraints="Use warm appetizing lighting that emphasizes gloss, crumb texture, steam, moisture, and believable plated contact.",
        allowed_props=("fork", "linen napkin", "seasoning crumbs", "soft steam detail"),
        props_required=True,
    ),
    "electronic_flat": DomainConstraint(
        sku_category="electronic_flat",
        recommended_camera_perspective="top-down or eye-level product view",
        physics_constraints="Maintain sharp metallic and glass reflections, crisp edge geometry, and strictly avoid blurry soft consumer-grade lighting.",
        allowed_props=("minimal cable", "keyboard", "tech light beam"),
    ),
}


def get_domain_constraint(sku_category: str | None) -> DomainConstraint | None:
    normalized = str(sku_category or "").strip().lower()
    return DOMAIN_CONSTRAINTS.get(normalized)


def get_category_constraint(sku_category: str | None) -> str:
    constraint = get_domain_constraint(sku_category)
    return constraint.physics_constraints if constraint else ""


def get_negative_prompt_lock(sku_category: str | None) -> str:
    constraint = get_domain_constraint(sku_category)
    return constraint.negative_prompt if constraint else ""


def get_prompt_prefix(sku_category: str | None) -> str:
    constraint = get_domain_constraint(sku_category)
    return constraint.prompt_prefix if constraint else ""


def get_perspective_lock(sku_category: str | None) -> str:
    constraint = get_domain_constraint(sku_category)
    return constraint.perspective_lock if constraint else ""


def _contains_any_keyword(text: str | None, keywords: set[str]) -> bool:
    normalized = " ".join(str(text or "").strip().lower().split())
    if not normalized:
        return False
    return any(keyword in normalized for keyword in keywords)


def is_soft_apparel_product_description(primary_sku_description: str | None) -> bool:
    return _contains_any_keyword(primary_sku_description, SOFT_APPAREL_DESCRIPTION_KEYWORDS)


def normalize_material_type(material_type: str | None) -> str:
    normalized = " ".join(str(material_type or "").strip().lower().split())
    if normalized in SUPPORTED_MATERIAL_TYPES:
        return normalized
    return ""


def resolve_material_type(
    material_type: str | None,
    primary_sku_description: str | None,
    sku_category: str | None = None,
) -> str:
    normalized_material_type = normalize_material_type(material_type)
    if normalized_material_type:
        return normalized_material_type

    normalized_category = str(sku_category or "").strip().lower()
    if normalized_category in {"beauty_bottle", "beauty_bottle_standing", "bottle_standing"}:
        return "reflective_glass"

    if _contains_any_keyword(primary_sku_description, GLASS_LIQUID_MATERIAL_KEYWORDS):
        return "reflective_glass"
    if _contains_any_keyword(primary_sku_description, LEATHER_PU_MATERIAL_KEYWORDS):
        return "leather_or_pu"
    if _contains_any_keyword(primary_sku_description, STIFF_FABRIC_MATERIAL_KEYWORDS):
        return "fabric_stiff"
    if _contains_any_keyword(primary_sku_description, KNIT_FLEECE_MATERIAL_KEYWORDS):
        return "fabric_soft"
    if is_soft_apparel_product_description(primary_sku_description):
        return "fabric_soft"

    return "matte_solid"


def is_physics_mutex_violation(
    *,
    sku_category: str | None,
    material_type: str | None,
    primary_sku_description: str | None,
) -> bool:
    normalized_category = str(sku_category or "").strip().lower()
    pose_alias = CATEGORY_POSE_ALIASES.get(normalized_category, normalized_category)
    effective_material_type = resolve_material_type(
        material_type,
        primary_sku_description,
        normalized_category,
    )

    if effective_material_type == "fabric_soft":
        return pose_alias in INVALID_CATEGORY_POSES["apparel_flat"]

    return False


def resolve_material_lighting_prompt(
    material_type: str | None,
    primary_sku_description: str | None,
    existing_prompt: str | None = None,
) -> str:
    normalized_existing = " ".join(str(existing_prompt or "").split()).strip()
    effective_material_type = resolve_material_type(
        material_type,
        primary_sku_description,
    )
    material_prompt = MATERIAL_LIGHTING_RULES.get(effective_material_type, "")
    if not material_prompt:
        return normalized_existing

    if not normalized_existing:
        return material_prompt

    if material_prompt.lower() in normalized_existing.lower():
        return normalized_existing

    return f"{material_prompt} {normalized_existing}"


def resolve_camera_perspective(
    camera_perspective: str | None,
    sku_category: str | None,
) -> str:
    normalized = " ".join(str(camera_perspective or "").split()).strip()
    if normalized:
        return normalized

    constraint = get_domain_constraint(sku_category)
    if constraint:
        return constraint.recommended_camera_perspective
    return DEFAULT_CAMERA_PERSPECTIVE


def build_camera_perspective_sentence(
    camera_perspective: str | None,
    sku_category: str | None,
) -> str:
    resolved = resolve_camera_perspective(camera_perspective, sku_category)
    if not resolved:
        return ""
    return f"Shot from a consistent {resolved} perspective."


def build_camera_perspective_constraint(
    camera_perspective: str | None,
    sku_category: str | None,
) -> str:
    resolved = resolve_camera_perspective(camera_perspective, sku_category)
    if not resolved:
        return ""

    normalized_sku_category = str(sku_category or "").strip().lower()
    if normalized_sku_category == "shoes_resting":
        return f"The background must be generated from the same {resolved} perspective as the original product."

    return f"Match the original reference camera perspective: {resolved}."


def filter_dynamic_props(
    *,
    dynamic_props: list[str] | None,
    sku_category: str | None,
    primary_sku_description: str | None,
) -> list[str]:
    normalized_sku_category = str(sku_category or "").strip().lower()
    constraint = get_domain_constraint(normalized_sku_category)
    if constraint and not constraint.allow_dynamic_props:
        return []

    primary_text = str(primary_sku_description or "").strip().lower()
    banned_terms = set(DEFAULT_PROP_RULES["banned_terms"])
    if constraint:
        banned_terms.update(term.lower() for term in constraint.banned_props)

    allow_watch = any(keyword in primary_text for keyword in ("watch", "business", "briefcase", "formal office"))
    if allow_watch:
        banned_terms.discard("watch")

    normalized_props: list[str] = []
    seen: set[str] = set()
    for item in dynamic_props or []:
        prop = " ".join(str(item).split()).strip()
        lowered = prop.lower()
        if not prop or lowered in seen:
            continue
        if any(term in lowered for term in banned_terms):
            continue
        seen.add(lowered)
        normalized_props.append(prop)
        if len(normalized_props) >= 2:
            break

    if normalized_props:
        if "straw bag" in primary_text:
            return ["straw hat", "sunscreen"]
        return normalized_props

    if "straw bag" in primary_text:
        return ["straw hat", "sunscreen"]

    if constraint and constraint.allowed_props:
        return list(constraint.allowed_props[:2])

    return []
