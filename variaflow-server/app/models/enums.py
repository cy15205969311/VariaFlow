from __future__ import annotations

from enum import Enum


class BatchStatus(str, Enum):
    PENDING = "pending"
    INGESTING = "ingesting"
    READY = "ready"
    RUNNING = "running"
    PARTIAL_SUCCESS = "partial_success"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class UploadMode(str, Enum):
    ZIP = "zip"
    FOLDER = "folder"


class ExportStatus(str, Enum):
    NOT_REQUESTED = "not_requested"
    QUEUED = "queued"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"


class SourceTaskStatus(str, Enum):
    PENDING = "pending"
    PARTIAL_SUCCESS = "partial_success"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    FALLBACK_SUCCESS = "fallback_success"
    RETRYING = "retrying"


class VariantAxis(str, Enum):
    ACTION = "action"
    OUTFIT = "outfit"
    SCENE = "scene"
    MIXED = "mixed"


class ProviderRoute(str, Enum):
    PRIMARY = "primary"
    FALLBACK = "fallback"


class AttemptOutcome(str, Enum):
    STARTED = "started"
    SUCCESS = "success"
    RETRYABLE_ERROR = "retryable_error"
    FATAL_ERROR = "fatal_error"
    TIMEOUT = "timeout"
    QC_FAILED = "qc_failed"


class QCStatus(str, Enum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class QCMode(str, Enum):
    RULES_ONLY = "rules_only"
    HYBRID = "hybrid"


class QCVerdict(str, Enum):
    PASSED = "passed"
    FAILED = "failed"


class VariantGenerationMode(str, Enum):
    MATRIX = "matrix"
    MANUAL = "manual"
