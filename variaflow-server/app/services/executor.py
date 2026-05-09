from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.gateways.ai_provider import call_ai_provider
from app.models.enums import (
    AttemptOutcome,
    BatchStatus,
    ProviderRoute,
    QCMode,
    QCVerdict,
    QCStatus,
    SourceTaskStatus,
    TaskStatus,
)
from app.models.tasks import (
    BatchJob,
    BatchPromptConfig,
    GenerationAttempt,
    GenerationTask,
    PromptProfile,
    QualityCheckResult as QualityCheckResultModel,
    SourceTask,
)
from app.services.generation import finalize_generation_task
from app.services.prompt_builder import build_provider_payload
from app.services.qc_engine import QualityCheckResult
from app.services.qc_engine import run_rules_qc

DEFAULT_QC_CONFIG = {
    "min_file_size_bytes": 51_200,
    "min_width": 1024,
    "min_height": 1024,
    "allowed_mime_types": {"image/png", "image/jpeg", "image/webp"},
}


@dataclass(slots=True)
class ExecutionContext:
    task_id: int
    attempt_no: int
    batch_id: int
    source_index: int
    variant_index: int
    batch_output_root: Path
    payload: dict[str, Any]
    prompt_snapshot: dict[str, Any]


def _payload_hash(payload: dict[str, Any]) -> str:
    normalized = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


async def _load_generation_context(
    session: AsyncSession,
    task_id: int,
) -> tuple[GenerationTask, PromptProfile | None, BatchPromptConfig | None]:
    statement = (
        select(GenerationTask)
        .where(GenerationTask.id == task_id)
        .options(
            selectinload(GenerationTask.source_task).selectinload(SourceTask.batch).selectinload(BatchJob.prompt_config),
        )
    )
    task = (await session.execute(statement)).scalar_one_or_none()
    if task is None:
        raise ValueError(f"未找到生成任务：{task_id}")

    batch_config = task.source_task.batch.prompt_config if task.source_task and task.source_task.batch else None
    profile_id = batch_config.prompt_profile_id if batch_config else None

    prompt_profile: PromptProfile | None = None
    if profile_id is not None:
        profile_stmt = (
            select(PromptProfile)
            .where(PromptProfile.id == profile_id, PromptProfile.is_active.is_(True))
            .options(selectinload(PromptProfile.variable_options))
        )
        prompt_profile = (await session.execute(profile_stmt)).scalar_one_or_none()

    if prompt_profile is None:
        default_profile_stmt = (
            select(PromptProfile)
            .where(PromptProfile.is_default.is_(True), PromptProfile.is_active.is_(True))
            .options(selectinload(PromptProfile.variable_options))
        )
        prompt_profile = (await session.execute(default_profile_stmt)).scalar_one_or_none()

    return task, prompt_profile, batch_config


async def _prepare_execution_context(
    session: AsyncSession,
    task_id: int,
) -> ExecutionContext:
    task, prompt_profile, batch_config = await _load_generation_context(session, task_id)
    payload, prompt_snapshot = build_provider_payload(
        task.source_task,
        task,
        prompt_profile,
        batch_config,
    )

    task.prompt_snapshot_json = prompt_snapshot
    await session.commit()

    batch_output_root = Path(task.source_task.batch.output_root_path or settings.data_root / "outputs")
    return ExecutionContext(
        task_id=task.id,
        attempt_no=task.attempt_count,
        batch_id=task.batch_id,
        source_index=task.source_task.source_index,
        variant_index=task.variant_index,
        batch_output_root=batch_output_root,
        payload=payload,
        prompt_snapshot=prompt_snapshot,
    )


async def _create_attempt_record(
    session: AsyncSession,
    *,
    context: ExecutionContext,
    started_at: datetime,
    provider_route: ProviderRoute = ProviderRoute.PRIMARY,
    provider_code: str = "openai_image_2",
    outcome: AttemptOutcome = AttemptOutcome.STARTED,
    error_code: str | None = None,
    error_message: str | None = None,
    latency_ms: int | None = None,
    switch_reason: str | None = None,
    http_status: int | None = None,
) -> GenerationAttempt:
    attempt = GenerationAttempt(
        generation_task_id=context.task_id,
        attempt_no=context.attempt_no,
        provider_route=provider_route,
        provider_code=provider_code,
        request_payload_hash=_payload_hash(context.payload),
        request_payload_json=context.payload,
        started_at=started_at,
        finished_at=datetime.utcnow() if outcome != AttemptOutcome.STARTED else None,
        latency_ms=latency_ms,
        switch_reason=switch_reason,
        http_status=http_status,
        outcome=outcome,
        error_code=error_code,
        error_message=error_message,
    )
    session.add(attempt)
    await session.commit()
    await session.refresh(attempt)
    return attempt


async def _persist_qc_result(
    session: AsyncSession,
    *,
    task_id: int,
    attempt_id: int,
    qc_result: QualityCheckResult,
) -> None:
    qc_row = QualityCheckResultModel(
        generation_task_id=task_id,
        generation_attempt_id=attempt_id,
        qc_mode=QCMode.RULES_ONLY,
        verdict=QCVerdict.PASSED if qc_result.passed else QCVerdict.FAILED,
        rules_passed=qc_result.passed,
        model_passed=None,
        min_file_size_ok=qc_result.min_file_size_ok,
        resolution_ok=qc_result.resolution_ok,
        mime_type_ok=qc_result.mime_type_ok,
        fail_codes_json=qc_result.fail_codes,
        metrics_json=qc_result.to_metrics(),
    )
    session.add(qc_row)
    await session.commit()


async def _recompute_source_and_batch_state(session: AsyncSession, *, task_id: int) -> None:
    generation_task = (
        await session.execute(
            select(GenerationTask)
            .where(GenerationTask.id == task_id)
            .options(
                selectinload(GenerationTask.source_task).selectinload(SourceTask.generation_tasks),
                selectinload(GenerationTask.batch).selectinload(BatchJob.source_tasks),
            )
        )
    ).scalar_one()

    source_task = generation_task.source_task
    batch = generation_task.batch

    success_statuses = {TaskStatus.SUCCESS, TaskStatus.FALLBACK_SUCCESS}
    failure_statuses = {TaskStatus.FAILED}
    active_statuses = {TaskStatus.PENDING, TaskStatus.PROCESSING, TaskStatus.RETRYING}
    source_task.success_count = sum(1 for item in source_task.generation_tasks if item.status in success_statuses)
    source_task.failed_count = sum(1 for item in source_task.generation_tasks if item.status in failure_statuses)
    source_active_count = sum(1 for item in source_task.generation_tasks if item.status in active_statuses)

    if source_task.success_count >= source_task.target_variant_count:
        source_task.status = SourceTaskStatus.COMPLETED
    elif source_task.success_count > 0 and source_active_count == 0:
        source_task.status = SourceTaskStatus.PARTIAL_SUCCESS
    elif source_task.success_count > 0:
        source_task.status = SourceTaskStatus.PARTIAL_SUCCESS
    elif source_task.failed_count >= source_task.target_variant_count:
        source_task.status = SourceTaskStatus.FAILED
    else:
        source_task.status = SourceTaskStatus.PENDING

    source_statuses = [item.status for item in batch.source_tasks]
    batch.completed_source_count = sum(1 for status in source_statuses if status == SourceTaskStatus.COMPLETED)
    batch.partial_source_count = sum(1 for status in source_statuses if status == SourceTaskStatus.PARTIAL_SUCCESS)
    batch.failed_source_count = sum(1 for status in source_statuses if status == SourceTaskStatus.FAILED)
    batch.success_generation_count = (
        await session.execute(
            select(func.count()).select_from(GenerationTask).where(
                GenerationTask.batch_id == batch.id,
                GenerationTask.status.in_(success_statuses),
            )
        )
    ).scalar_one()
    batch.failed_generation_count = (
        await session.execute(
            select(func.count()).select_from(GenerationTask).where(
                GenerationTask.batch_id == batch.id,
                GenerationTask.status == TaskStatus.FAILED,
            )
        )
    ).scalar_one()
    terminal_generation_count = batch.success_generation_count + batch.failed_generation_count

    if batch.completed_source_count == batch.total_source_count and batch.total_source_count > 0:
        batch.status = BatchStatus.COMPLETED
        batch.scheduler_finished_at = datetime.utcnow()
    elif terminal_generation_count == batch.total_generation_count and batch.total_generation_count > 0:
        batch.status = (
            BatchStatus.PARTIAL_SUCCESS
            if batch.success_generation_count > 0 or batch.partial_source_count > 0 or batch.completed_source_count > 0
            else BatchStatus.FAILED
        )
        batch.scheduler_finished_at = datetime.utcnow()
    else:
        batch.status = BatchStatus.RUNNING
        batch.scheduler_finished_at = None

    await session.commit()


async def _mark_task_for_retry_or_failure(
    session: AsyncSession,
    *,
    context: ExecutionContext,
    outcome: AttemptOutcome,
    error_code: str,
    error_message: str,
    provider_route: ProviderRoute,
    provider_code: str,
    http_status: int | None,
    switch_reason: str | None,
    latency_ms: int,
    response_meta: dict[str, Any] | None = None,
) -> None:
    task = (await session.execute(select(GenerationTask).where(GenerationTask.id == context.task_id))).scalar_one()
    attempt = (
        await session.execute(
            select(GenerationAttempt).where(
                GenerationAttempt.generation_task_id == context.task_id,
                GenerationAttempt.attempt_no == context.attempt_no,
            )
        )
    ).scalar_one_or_none()

    if attempt is None:
        attempt = GenerationAttempt(
            generation_task_id=context.task_id,
            attempt_no=context.attempt_no,
            provider_route=provider_route,
            provider_code=provider_code,
            request_payload_hash=_payload_hash(context.payload),
            request_payload_json=context.payload,
            started_at=datetime.utcnow(),
            outcome=AttemptOutcome.STARTED,
        )
        session.add(attempt)

    attempt.provider_route = provider_route
    attempt.provider_code = provider_code
    attempt.http_status = http_status
    attempt.switch_reason = switch_reason
    attempt.finished_at = datetime.utcnow()
    attempt.latency_ms = latency_ms
    attempt.outcome = outcome
    attempt.error_code = error_code
    attempt.error_message = error_message
    if response_meta:
        attempt.response_meta_json = response_meta

    should_retry = task.attempt_count < task.max_attempts and outcome in {
        AttemptOutcome.RETRYABLE_ERROR,
        AttemptOutcome.TIMEOUT,
        AttemptOutcome.QC_FAILED,
    }
    task.status = TaskStatus.RETRYING if should_retry else TaskStatus.FAILED
    task.next_run_at = None
    if should_retry:
        task.next_run_at = datetime.utcnow() + timedelta(seconds=min(60, 5 * max(task.attempt_count, 1)))
    task.lease_owner = None
    task.lease_until = None
    task.last_error_code = error_code
    task.last_error_message = error_message
    task.last_provider_http_status = http_status
    task.last_switch_reason = switch_reason
    if outcome == AttemptOutcome.QC_FAILED:
        task.qc_status = QCStatus.FAILED
    if not should_retry:
        task.completed_at = datetime.utcnow()

    await session.commit()
    await _recompute_source_and_batch_state(session, task_id=context.task_id)


async def process_generation_task(
    task_id: int,
    db_session_factory: async_sessionmaker[AsyncSession] = AsyncSessionLocal,
) -> None:
    """
    执行单个生成任务，严格分为四个阶段：

    1. 数据库阶段：读取任务与 Prompt 配置，随后释放会话。
    2. 网络与文件阶段：调用模型网关并写入本地临时文件。
    3. 本地质检阶段：对临时文件执行规则校验。
    4. 数据库收尾阶段：重新开新会话写入 attempt、QC 与最终任务状态。
    """

    context: ExecutionContext | None = None
    provider_route = ProviderRoute.PRIMARY
    provider_code = "openai_image_2"
    switch_reason: str | None = None
    http_status: int | None = None
    response_meta: dict[str, Any] = {}
    temp_file: Path | None = None
    attempt_id: int | None = None
    started_at = datetime.utcnow()

    try:
        async with db_session_factory() as session:
            context = await _prepare_execution_context(session, task_id)
        async with db_session_factory() as session:
            attempt = await _create_attempt_record(
                session,
                context=context,
                started_at=started_at,
            )
            attempt_id = attempt.id

        try:
            image_bytes, response_meta = await call_ai_provider(context.payload, ProviderRoute.PRIMARY)
            provider_route = ProviderRoute(response_meta.get("provider_route", ProviderRoute.PRIMARY.value))
            provider_code = str(response_meta.get("provider_code", provider_code))
            switch_reason = response_meta.get("switch_reason")
            http_status = response_meta.get("http_status")
        except Exception as exc:
            latency_ms = int((datetime.utcnow() - started_at).total_seconds() * 1000)
            switch_reason = getattr(exc, "switch_reason", switch_reason)
            provider_route_value = getattr(exc, "provider_route", provider_route.value)
            provider_code = str(getattr(exc, "provider_code", provider_code))
            provider_route = ProviderRoute(provider_route_value)
            outcome = AttemptOutcome.RETRYABLE_ERROR
            error_code = "provider_error"
            if isinstance(exc, httpx.TimeoutException):
                outcome = AttemptOutcome.TIMEOUT
                error_code = "provider_timeout"
            elif isinstance(exc, httpx.HTTPStatusError):
                http_status = exc.response.status_code
                if http_status not in {429, 502, 503, 504}:
                    outcome = AttemptOutcome.FATAL_ERROR
                error_code = f"provider_http_{http_status}"

            async with db_session_factory() as session:
                await _mark_task_for_retry_or_failure(
                    session,
                    context=context,
                    outcome=outcome,
                    error_code=error_code,
                    error_message=str(exc),
                    provider_route=provider_route,
                    provider_code=provider_code,
                    http_status=http_status,
                    switch_reason=switch_reason,
                    latency_ms=latency_ms,
                    response_meta=response_meta,
                )
            return

        tmp_dir = context.batch_output_root.parent / "tmp"
        temp_file = tmp_dir / f"{context.task_id}_attempt_{context.attempt_no}.part"
        await asyncio.to_thread(tmp_dir.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(temp_file.write_bytes, image_bytes)

        qc_result = await asyncio.to_thread(
            run_rules_qc,
            str(temp_file),
            DEFAULT_QC_CONFIG["min_file_size_bytes"],
            DEFAULT_QC_CONFIG["min_width"],
            DEFAULT_QC_CONFIG["min_height"],
            DEFAULT_QC_CONFIG["allowed_mime_types"],
        )
        latency_ms = int((datetime.utcnow() - started_at).total_seconds() * 1000)

        async with db_session_factory() as session:
            attempt = (
                await session.execute(
                    select(GenerationAttempt).where(
                        GenerationAttempt.generation_task_id == context.task_id,
                        GenerationAttempt.attempt_no == context.attempt_no,
                    )
                )
            ).scalar_one()
            attempt.http_status = http_status
            attempt.switch_reason = switch_reason
            attempt.response_meta_json = response_meta
            attempt.provider_route = provider_route
            attempt.provider_code = provider_code
            attempt.latency_ms = latency_ms
            await session.commit()
            await _persist_qc_result(session, task_id=context.task_id, attempt_id=attempt.id, qc_result=qc_result)

        if not qc_result.passed:
            async with db_session_factory() as session:
                task_row = (await session.execute(select(GenerationTask).where(GenerationTask.id == context.task_id))).scalar_one()
                task_row.qc_status = QCStatus.FAILED
                task_row.qc_fail_codes_json = qc_result.fail_codes
                await session.commit()
                await _mark_task_for_retry_or_failure(
                    session,
                    context=context,
                    outcome=AttemptOutcome.QC_FAILED,
                    error_code="qc_failed",
                    error_message="; ".join(qc_result.fail_codes) or "规则质检未通过",
                    provider_route=provider_route,
                    provider_code=provider_code,
                    http_status=http_status,
                    switch_reason=switch_reason,
                    latency_ms=latency_ms,
                    response_meta=response_meta,
                )
            if temp_file is not None and temp_file.exists():
                await asyncio.to_thread(temp_file.unlink, True)
            return

        async with db_session_factory() as session:
            statement = (
                select(GenerationTask)
                .where(GenerationTask.id == context.task_id)
                .options(
                    selectinload(GenerationTask.source_task).selectinload(SourceTask.batch),
                    selectinload(GenerationTask.attempts),
                )
            )
            task_row = (await session.execute(statement)).scalar_one()
            attempt_row = next((item for item in task_row.attempts if item.attempt_no == context.attempt_no), None)
            if attempt_row is None:
                raise ValueError(f"未找到任务 {context.task_id} 的第 {context.attempt_no} 次尝试记录。")

            attempt_row.provider_route = provider_route
            attempt_row.provider_code = provider_code
            attempt_row.http_status = http_status
            attempt_row.switch_reason = switch_reason
            attempt_row.response_meta_json = response_meta
            attempt_row.latency_ms = latency_ms
            task_row.provider_final = provider_code

            final_output_path = (
                context.batch_output_root
                / f"S{context.source_index:04d}"
                / f"variant_{context.variant_index}.png"
            )
            await finalize_generation_task(
                session,
                task=task_row,
                attempt=attempt_row,
                image_bytes=image_bytes,
                final_output_path=final_output_path,
                tmp_dir=tmp_dir,
                provider_route=provider_route,
                min_file_size_bytes=DEFAULT_QC_CONFIG["min_file_size_bytes"],
                temp_path=temp_file,
            )
            await _recompute_source_and_batch_state(session, task_id=context.task_id)
    except Exception as exc:
        if context is None:
            return

        latency_ms = int((datetime.utcnow() - started_at).total_seconds() * 1000)
        async with db_session_factory() as session:
            await _mark_task_for_retry_or_failure(
                session,
                context=context,
                outcome=AttemptOutcome.FATAL_ERROR if attempt_id is None else AttemptOutcome.RETRYABLE_ERROR,
                error_code="executor_preflight_error" if attempt_id is None else "executor_runtime_error",
                error_message=str(exc),
                provider_route=provider_route,
                provider_code=provider_code,
                http_status=http_status,
                switch_reason=switch_reason,
                latency_ms=latency_ms,
                response_meta=response_meta,
            )
