from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    batch_code: str
    status: str
    upload_mode: str
    original_upload_name: str | None = None
    target_variant_count: int
    total_source_count: int
    total_generation_count: int
    completed_source_count: int
    partial_source_count: int
    failed_source_count: int
    success_generation_count: int
    failed_generation_count: int
    estimated_remaining_seconds: int | None = Field(default=None)
    created_at: datetime
    updated_at: datetime
