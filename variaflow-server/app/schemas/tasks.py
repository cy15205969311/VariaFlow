from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class GenerationTaskSlotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    variant_index: int
    variant_axis: str
    intent: str | None = None
    intent_label: str | None = None
    intent_reason: str | None = None
    subject_type: str | None = None
    sku_category: str | None = None
    suggested_scene: str | None = None
    suggested_scene_recipe: str | None = None
    dynamic_spatial_anchor: str | None = None
    dynamic_lighting_needs: str | None = None
    primary_sku_description: str | None = None
    secondary_props: str | None = None
    dynamic_props: list[str] | None = None
    camera_perspective: str | None = None
    subject_features: str | None = None
    style_features: str | None = None
    background_features: str | None = None
    status: str
    provider_final: str | None = None
    provider_route_final: str | None = None
    attempt_count: int
    max_attempts: int
    output_path: str | None = None
    output_file_name: str | None = None
    qc_status: str
    last_error_code: str | None = None
    last_error_message: str | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    batch_id: int
    source_index: int
    status: str
    source_name: str
    source_path: str
    normalized_path: str | None = None
    source_hash: str
    target_variant_count: int
    success_count: int
    failed_count: int
    created_at: datetime
    updated_at: datetime
    generation_tasks: list[GenerationTaskSlotResponse]


class TaskListResponse(BaseModel):
    items: list[TaskResponse]
    total: int
    page: int
    page_size: int
