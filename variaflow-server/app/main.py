from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.router import api_router
from app.api.deps import get_db
from app.core.config import settings
from app.core.database import close_engine
from app.services.scheduler import run_recovery_loop, run_scheduler_loop

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def _run_named_background_task(name: str, coroutine: Awaitable[None]) -> None:
    """
    为长生命周期循环增加保护包装，确保异常会被明确记录。

    子循环本身应当捕获可恢复错误并继续运行。
    这里的包装层只负责避免后台任务悄无声息地退出。
    """

    try:
        await coroutine
    except asyncio.CancelledError:
        logger.info("后台任务已取消", extra={"task_name": name})
        raise
    except Exception:
        logger.exception("后台任务发生崩溃", extra={"task_name": name})
        raise


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    scheduler_task = asyncio.create_task(
        _run_named_background_task(
            "scheduler_loop",
            run_scheduler_loop(
                poll_interval_seconds=settings.scheduler_poll_interval_seconds,
                lease_seconds=settings.worker_lease_seconds,
                worker_name=settings.worker_name,
            ),
        ),
        name="scheduler_loop",
    )
    recovery_task = asyncio.create_task(
        _run_named_background_task(
            "recovery_loop",
            run_recovery_loop(
                poll_interval_seconds=settings.recovery_interval_seconds,
            ),
        ),
        name="recovery_loop",
    )

    app.state.scheduler_task = scheduler_task
    app.state.recovery_task = recovery_task

    try:
        yield
    finally:
        for task in (scheduler_task, recovery_task):
            task.cancel()

        for task in (scheduler_task, recovery_task):
            with contextlib.suppress(asyncio.CancelledError):
                await task

        await close_engine()


app = FastAPI(title="VariaFlow API", debug=settings.debug, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_allow_origins) or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount(
    "/static",
    StaticFiles(directory=str(settings.data_root), check_dir=False),
    name="static",
)

app.include_router(api_router)


@app.get("/health")
async def health_check(session: AsyncSession = Depends(get_db)) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    return {"status": "ok"}
