from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class GenerationTaskSlotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    variant_index: int
    variant_axis: str
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
