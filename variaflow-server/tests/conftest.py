from __future__ import annotations

import asyncio
import shutil
import sys
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings
from app.models.base import Base
from app.models.enums import (
    BatchStatus,
    ExportStatus,
    SourceTaskStatus,
    TaskStatus,
    UploadMode,
    VariantAxis,
)
from app.models.tasks import (
    BatchJob,
    BatchPromptConfig,
    GenerationTask,
    PromptProfile,
    SourceTask,
)


def _ensure_test_database_isolation() -> None:
    if not settings.is_test_env:
        raise RuntimeError("当前不是测试环境，已阻止加载测试夹具。")
    if not settings.test_database_url:
        raise RuntimeError("未配置 VARIAFLOW_TEST_DATABASE_URL，无法启动测试。")
    if settings.effective_database_url != settings.test_database_url:
        raise RuntimeError("测试会话未绑定测试数据库，已阻止继续执行。")


def _safe_remove_tree(path: Path) -> None:
    try:
        if not path.exists():
            return
        if path.name.startswith("test_batch_") and path.parent.resolve() == settings.data_root.resolve():
            shutil.rmtree(path, ignore_errors=True)
    except OSError as exc:
        print(f"清理测试目录失败：{path}，原因：{exc}")


_ensure_test_database_isolation()

TEST_ENGINE: AsyncEngine = create_async_engine(
    settings.test_database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    poolclass=NullPool,
    future=True,
)
TestSessionLocal = async_sessionmaker(
    bind=TEST_ENGINE,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


@pytest.fixture(scope="session")
def event_loop() -> AsyncIterator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()


@pytest_asyncio.fixture(scope="session")
async def prepare_test_schema() -> AsyncIterator[None]:
    # 显式导入模型模块，确保 Base.metadata 已完整注册所有表结构。
    import app.models.tasks  # noqa: F401

    async with TEST_ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    try:
        yield
    finally:
        async with TEST_ENGINE.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await TEST_ENGINE.dispose()


@pytest_asyncio.fixture
async def db_session(prepare_test_schema: None) -> AsyncIterator[AsyncSession]:
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def mock_batch_data(prepare_test_schema: None) -> AsyncIterator[dict[str, object]]:
    batch_code = f"test_batch_{uuid.uuid4().hex[:10]}"
    batch_root = settings.data_root / batch_code
    normalized_root = batch_root / "normalized"
    output_root = batch_root / "outputs"
    failed_root = batch_root / "failed"
    tmp_root = batch_root / "tmp"

    for path in (normalized_root, output_root, failed_root, tmp_root):
        await asyncio.to_thread(path.mkdir, parents=True, exist_ok=True)

    normalized_file = normalized_root / "S0001_src_mock.png"
    normalized_file.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
        b"\x90wS\xde"
        b"\x00\x00\x00\x0cIDAT\x08\xd7c\xf8\xff\xff?\x00\x05\xfe\x02\xfeA\xa5\x1d\xb1"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    batch = BatchJob(
        batch_code=batch_code,
        status=BatchStatus.RUNNING,
        upload_mode=UploadMode.ZIP,
        original_upload_name="pytest_sandbox.zip",
        input_archive_path=str(batch_root / "input_archive" / "pytest_sandbox.zip"),
        input_root_path=str(batch_root / "input_archive"),
        unzip_root_path=str(batch_root / "input_unpacked"),
        normalized_root_path=str(normalized_root),
        output_root_path=str(output_root),
        failed_root_path=str(failed_root),
        export_status=ExportStatus.NOT_REQUESTED,
        target_variant_count=2,
        total_source_count=1,
        total_generation_count=2,
    )
    prompt_profile = PromptProfile(
        profile_code=f"pytest_default_{uuid.uuid4().hex[:8]}",
        profile_name="pytest 默认提示词",
        positive_template="保持主体一致，{{identity_lock}}，执行变化：{{variant_directive}}。",
        negative_template="不要模糊，不要水印，不要畸形。",
        identity_template="保持同一主体识别特征。",
        quality_template="电商主图，主体完整，高清。",
        is_default=True,
        is_active=True,
    )
    source_task = SourceTask(
        batch=batch,
        source_index=1,
        status=SourceTaskStatus.PENDING,
        source_name=normalized_file.name,
        source_ext="png",
        source_relative_path=normalized_file.name,
        source_path=str(normalized_file),
        normalized_path=str(normalized_file),
        source_hash=uuid.uuid4().hex * 2,
        source_size_bytes=normalized_file.stat().st_size,
        target_variant_count=2,
        success_count=0,
        failed_count=0,
        identity_profile_json={"identity_lock": "保持参考图中的同一主体身份特征。"},
    )
    prompt_config = BatchPromptConfig(
        batch=batch,
        prompt_profile=prompt_profile,
        positive_override=None,
        negative_override=None,
        identity_lock_override=None,
        quality_override=None,
    )
    generation_tasks = [
        GenerationTask(
            batch=batch,
            source_task=source_task,
            variant_index=variant_index,
            variant_axis=VariantAxis.MIXED,
            status=TaskStatus.PENDING,
            attempt_count=0,
            max_attempts=3,
        )
        for variant_index in range(1, 3)
    ]

    async with TestSessionLocal() as session:
        session.add(batch)
        session.add(prompt_profile)
        session.add(source_task)
        session.add(prompt_config)
        session.add_all(generation_tasks)
        await session.commit()
        await session.refresh(batch)
        await session.refresh(source_task)
        for task in generation_tasks:
            await session.refresh(task)

    generation_task_ids = [task.id for task in generation_tasks]
    payload = {
        "batch_id": batch.id,
        "batch_code": batch_code,
        "batch_root": batch_root,
        "normalized_root": normalized_root,
        "output_root": output_root,
        "failed_root": failed_root,
        "tmp_root": tmp_root,
        "source_task_id": source_task.id,
        "generation_task_ids": generation_task_ids,
        "session_factory": TestSessionLocal,
    }

    try:
        yield payload
    finally:
        async with TestSessionLocal() as session:
            await session.execute(Base.metadata.tables["quality_check_result"].delete())
            await session.execute(Base.metadata.tables["generation_attempt"].delete())
            await session.execute(Base.metadata.tables["generation_task"].delete())
            await session.execute(Base.metadata.tables["batch_prompt_config"].delete())
            await session.execute(Base.metadata.tables["source_task"].delete())
            await session.execute(Base.metadata.tables["prompt_profile"].delete())
            await session.execute(Base.metadata.tables["batch_job"].delete())
            await session.commit()

        await asyncio.to_thread(_safe_remove_tree, batch_root)
