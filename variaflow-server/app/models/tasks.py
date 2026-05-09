from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    CHAR,
    BigInteger,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import BIGINT, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import (
    AttemptOutcome,
    BatchStatus,
    ExportStatus,
    ProviderRoute,
    QCMode,
    QCStatus,
    QCVerdict,
    SourceTaskStatus,
    TaskStatus,
    UploadMode,
    VariantAxis,
    VariantGenerationMode,
)


def enum_values(enum_cls: type) -> list[str]:
    return [member.value for member in enum_cls]


class BatchJob(Base):
    __tablename__ = "batch_job"

    __table_args__ = (
        Index("idx_batch_job_status_created_at", "status", "created_at"),
        Index("idx_batch_job_export_status", "export_status", "updated_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger().with_variant(BIGINT(unsigned=True), "mysql"), primary_key=True, autoincrement=True)
    batch_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[BatchStatus] = mapped_column(
        SqlEnum(BatchStatus, values_callable=enum_values, name="batch_status"),
        default=BatchStatus.PENDING,
        nullable=False,
    )
    upload_mode: Mapped[UploadMode] = mapped_column(
        SqlEnum(UploadMode, values_callable=enum_values, name="upload_mode"),
        nullable=False,
    )
    original_upload_name: Mapped[str | None] = mapped_column(String(255))
    input_archive_path: Mapped[str | None] = mapped_column(String(1024))
    input_root_path: Mapped[str | None] = mapped_column(String(1024))
    unzip_root_path: Mapped[str | None] = mapped_column(String(1024))
    normalized_root_path: Mapped[str | None] = mapped_column(String(1024))
    output_root_path: Mapped[str | None] = mapped_column(String(1024))
    failed_root_path: Mapped[str | None] = mapped_column(String(1024))
    export_zip_path: Mapped[str | None] = mapped_column(String(1024))
    export_status: Mapped[ExportStatus] = mapped_column(
        SqlEnum(ExportStatus, values_callable=enum_values, name="export_status"),
        default=ExportStatus.NOT_REQUESTED,
        nullable=False,
    )
    target_variant_count: Mapped[int] = mapped_column(SmallInteger, default=3, nullable=False)
    total_source_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_generation_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_source_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    partial_source_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_source_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_generation_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_generation_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    scheduler_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    scheduler_finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    exported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    last_error_code: Mapped[str | None] = mapped_column(String(64))
    last_error_message: Mapped[str | None] = mapped_column(String(1024))
    created_by: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    source_tasks: Mapped[list["SourceTask"]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="SourceTask.source_index",
    )
    generation_tasks: Mapped[list["GenerationTask"]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    prompt_config: Mapped["BatchPromptConfig | None"] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )


class SourceTask(Base):
    __tablename__ = "source_task"

    __table_args__ = (
        UniqueConstraint("batch_id", "source_index", name="uk_source_task_batch_source_index"),
        Index("idx_source_task_batch_status", "batch_id", "status", "source_index"),
        Index("idx_source_task_hash", "source_hash"),
    )

    id: Mapped[int] = mapped_column(BigInteger().with_variant(BIGINT(unsigned=True), "mysql"), primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batch_job.id", ondelete="CASCADE"), nullable=False)
    source_index: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[SourceTaskStatus] = mapped_column(
        SqlEnum(SourceTaskStatus, values_callable=enum_values, name="source_task_status"),
        default=SourceTaskStatus.PENDING,
        nullable=False,
    )
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_ext: Mapped[str] = mapped_column(String(16), nullable=False)
    source_relative_path: Mapped[str | None] = mapped_column(String(1024))
    source_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    normalized_path: Mapped[str | None] = mapped_column(String(1024))
    source_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    source_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_width: Mapped[int | None] = mapped_column(Integer)
    source_height: Mapped[int | None] = mapped_column(Integer)
    target_variant_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    success_count: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    identity_profile_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    last_error_code: Mapped[str | None] = mapped_column(String(64))
    last_error_message: Mapped[str | None] = mapped_column(String(1024))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    batch: Mapped[BatchJob] = relationship(back_populates="source_tasks")
    generation_tasks: Mapped[list["GenerationTask"]] = relationship(
        back_populates="source_task",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="GenerationTask.variant_index",
    )


class GenerationTask(Base):
    __tablename__ = "generation_task"

    __table_args__ = (
        UniqueConstraint("source_task_id", "variant_index", name="uk_generation_task_source_variant"),
        Index("idx_generation_task_scheduler", "status", "next_run_at", "lease_until", "id"),
        Index("idx_generation_task_batch_status", "batch_id", "status", "id"),
        Index("idx_generation_task_source_status", "source_task_id", "status", "id"),
        Index("idx_generation_task_manual_retry", "manual_retry_requested", "status", "next_run_at"),
        Index("idx_generation_task_output_hash", "output_hash"),
    )

    id: Mapped[int] = mapped_column(BigInteger().with_variant(BIGINT(unsigned=True), "mysql"), primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batch_job.id", ondelete="CASCADE"), nullable=False)
    source_task_id: Mapped[int] = mapped_column(ForeignKey("source_task.id", ondelete="CASCADE"), nullable=False)
    variant_index: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    variant_axis: Mapped[VariantAxis] = mapped_column(
        SqlEnum(VariantAxis, values_callable=enum_values, name="variant_axis"),
        default=VariantAxis.MIXED,
        nullable=False,
    )
    status: Mapped[TaskStatus] = mapped_column(
        SqlEnum(TaskStatus, values_callable=enum_values, name="task_status"),
        default=TaskStatus.PENDING,
        nullable=False,
    )
    variant_plan_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    prompt_snapshot_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    provider_final: Mapped[str | None] = mapped_column(String(32))
    provider_route_final: Mapped[ProviderRoute | None] = mapped_column(
        SqlEnum(ProviderRoute, values_callable=enum_values, name="provider_route")
    )
    attempt_count: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(SmallInteger, default=3, nullable=False)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    lease_owner: Mapped[str | None] = mapped_column(String(128))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    output_file_name: Mapped[str | None] = mapped_column(String(255))
    output_ext: Mapped[str | None] = mapped_column(String(16))
    output_path: Mapped[str | None] = mapped_column(String(1024))
    output_hash: Mapped[str | None] = mapped_column(CHAR(64))
    output_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    output_width: Mapped[int | None] = mapped_column(Integer)
    output_height: Mapped[int | None] = mapped_column(Integer)
    qc_status: Mapped[QCStatus] = mapped_column(
        SqlEnum(QCStatus, values_callable=enum_values, name="qc_status"),
        default=QCStatus.PENDING,
        nullable=False,
    )
    qc_fail_codes_json: Mapped[list[str] | None] = mapped_column(JSON)
    last_error_code: Mapped[str | None] = mapped_column(String(64))
    last_error_message: Mapped[str | None] = mapped_column(String(1024))
    last_provider_http_status: Mapped[int | None] = mapped_column(SmallInteger)
    last_switch_reason: Mapped[str | None] = mapped_column(String(64))
    manual_retry_requested: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    batch: Mapped[BatchJob] = relationship(back_populates="generation_tasks")
    source_task: Mapped[SourceTask] = relationship(back_populates="generation_tasks")
    attempts: Mapped[list["GenerationAttempt"]] = relationship(
        back_populates="generation_task",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="GenerationAttempt.attempt_no",
    )


class GenerationAttempt(Base):
    __tablename__ = "generation_attempt"

    __table_args__ = (
        UniqueConstraint("generation_task_id", "attempt_no", name="uk_generation_attempt_task_attempt_no"),
        Index("idx_generation_attempt_provider", "provider_code", "started_at"),
        Index("idx_generation_attempt_outcome", "outcome", "started_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger().with_variant(BIGINT(unsigned=True), "mysql"), primary_key=True, autoincrement=True)
    generation_task_id: Mapped[int] = mapped_column(ForeignKey("generation_task.id", ondelete="CASCADE"), nullable=False)
    attempt_no: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    provider_route: Mapped[ProviderRoute] = mapped_column(
        SqlEnum(ProviderRoute, values_callable=enum_values, name="attempt_provider_route"),
        nullable=False,
    )
    provider_code: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_request_id: Mapped[str | None] = mapped_column(String(128))
    request_payload_hash: Mapped[str | None] = mapped_column(CHAR(64))
    request_payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    response_meta_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    http_status: Mapped[int | None] = mapped_column(SmallInteger)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    switch_reason: Mapped[str | None] = mapped_column(String(64))
    outcome: Mapped[AttemptOutcome] = mapped_column(
        SqlEnum(AttemptOutcome, values_callable=enum_values, name="attempt_outcome"),
        nullable=False,
    )
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    temporary_file_path: Mapped[str | None] = mapped_column(String(1024))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow, nullable=False)

    generation_task: Mapped[GenerationTask] = relationship(back_populates="attempts")


class PromptProfile(Base):
    __tablename__ = "prompt_profile"

    __table_args__ = (
        Index("idx_prompt_profile_active", "is_active", "is_default"),
    )

    id: Mapped[int] = mapped_column(BigInteger().with_variant(BIGINT(unsigned=True), "mysql"), primary_key=True, autoincrement=True)
    profile_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    profile_name: Mapped[str] = mapped_column(String(128), nullable=False)
    subject_category: Mapped[str | None] = mapped_column(String(64))
    positive_template: Mapped[str] = mapped_column(Text, nullable=False)
    negative_template: Mapped[str] = mapped_column(Text, nullable=False)
    identity_template: Mapped[str | None] = mapped_column(Text)
    quality_template: Mapped[str | None] = mapped_column(Text)
    is_default: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    variable_options: Mapped[list["PromptVariableOption"]] = relationship(
        back_populates="prompt_profile",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    batch_configs: Mapped[list["BatchPromptConfig"]] = relationship(
        back_populates="prompt_profile",
        passive_deletes=True,
    )


class PromptVariableOption(Base):
    __tablename__ = "prompt_variable_option"

    __table_args__ = (
        UniqueConstraint("prompt_profile_id", "variable_type", "option_key", name="uk_prompt_variable_option"),
        Index("idx_prompt_variable_option_enabled", "prompt_profile_id", "variable_type", "is_enabled", "sort_order"),
    )

    id: Mapped[int] = mapped_column(BigInteger().with_variant(BIGINT(unsigned=True), "mysql"), primary_key=True, autoincrement=True)
    prompt_profile_id: Mapped[int] = mapped_column(ForeignKey("prompt_profile.id", ondelete="CASCADE"), nullable=False)
    variable_type: Mapped[str] = mapped_column(String(32), nullable=False)
    option_key: Mapped[str] = mapped_column(String(64), nullable=False)
    option_label: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_fragment: Mapped[str] = mapped_column(String(512), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    prompt_profile: Mapped[PromptProfile] = relationship(back_populates="variable_options")


class BatchPromptConfig(Base):
    __tablename__ = "batch_prompt_config"

    __table_args__ = (
        UniqueConstraint("batch_id", name="uk_batch_prompt_config_batch_id"),
        Index("idx_batch_prompt_config_profile", "prompt_profile_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger().with_variant(BIGINT(unsigned=True), "mysql"), primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batch_job.id", ondelete="CASCADE"), nullable=False)
    prompt_profile_id: Mapped[int | None] = mapped_column(ForeignKey("prompt_profile.id", ondelete="SET NULL"))
    variant_generation_mode: Mapped[VariantGenerationMode] = mapped_column(
        SqlEnum(VariantGenerationMode, values_callable=enum_values, name="variant_generation_mode"),
        default=VariantGenerationMode.MATRIX,
        nullable=False,
    )
    positive_override: Mapped[str | None] = mapped_column(Text)
    negative_override: Mapped[str | None] = mapped_column(Text)
    identity_lock_override: Mapped[str | None] = mapped_column(Text)
    quality_override: Mapped[str | None] = mapped_column(Text)
    selected_actions_json: Mapped[list[str] | dict[str, Any] | None] = mapped_column(JSON)
    selected_outfits_json: Mapped[list[str] | dict[str, Any] | None] = mapped_column(JSON)
    selected_scenes_json: Mapped[list[str] | dict[str, Any] | None] = mapped_column(JSON)
    selected_cameras_json: Mapped[list[str] | dict[str, Any] | None] = mapped_column(JSON)
    selected_styles_json: Mapped[list[str] | dict[str, Any] | None] = mapped_column(JSON)
    custom_variables_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    batch: Mapped[BatchJob] = relationship(back_populates="prompt_config")
    prompt_profile: Mapped[PromptProfile | None] = relationship(back_populates="batch_configs")


class QualityCheckResult(Base):
    __tablename__ = "quality_check_result"

    __table_args__ = (
        UniqueConstraint("generation_attempt_id", name="uk_quality_check_result_attempt"),
        Index("idx_quality_check_result_task_verdict", "generation_task_id", "verdict", "checked_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger().with_variant(BIGINT(unsigned=True), "mysql"), primary_key=True, autoincrement=True)
    generation_task_id: Mapped[int] = mapped_column(ForeignKey("generation_task.id", ondelete="CASCADE"), nullable=False)
    generation_attempt_id: Mapped[int] = mapped_column(ForeignKey("generation_attempt.id", ondelete="CASCADE"), nullable=False)
    qc_mode: Mapped[QCMode] = mapped_column(
        SqlEnum(QCMode, values_callable=enum_values, name="qc_mode"),
        default=QCMode.RULES_ONLY,
        nullable=False,
    )
    verdict: Mapped[QCVerdict] = mapped_column(
        SqlEnum(QCVerdict, values_callable=enum_values, name="qc_verdict"),
        nullable=False,
    )
    rules_passed: Mapped[bool] = mapped_column(default=False, nullable=False)
    model_passed: Mapped[bool | None] = mapped_column(default=None)
    min_file_size_ok: Mapped[bool] = mapped_column(default=False, nullable=False)
    resolution_ok: Mapped[bool] = mapped_column(default=False, nullable=False)
    mime_type_ok: Mapped[bool] = mapped_column(default=False, nullable=False)
    sharpness_score: Mapped[float | None] = mapped_column(nullable=True)
    watermark_score: Mapped[float | None] = mapped_column(nullable=True)
    anatomy_score: Mapped[float | None] = mapped_column(nullable=True)
    identity_similarity: Mapped[float | None] = mapped_column(nullable=True)
    duplicate_similarity: Mapped[float | None] = mapped_column(nullable=True)
    fail_codes_json: Mapped[list[str] | None] = mapped_column(JSON)
    metrics_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow, nullable=False)
