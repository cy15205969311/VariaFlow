from __future__ import annotations

from fastapi import APIRouter

from app.api.endpoints import batches, tasks

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(batches.router, prefix="/batches", tags=["batches"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
