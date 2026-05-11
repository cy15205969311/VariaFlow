from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy.exc import OperationalError

from app.services.recovery import is_retryable_lock_error


def _build_operational_error(code: int, message: str) -> OperationalError:
    original = SimpleNamespace(args=(code, message))
    return OperationalError("mock statement", {}, original)


def test_is_retryable_lock_error_detects_deadlock() -> None:
    exc = _build_operational_error(1213, "Deadlock found when trying to get lock")
    assert is_retryable_lock_error(exc) is True


def test_is_retryable_lock_error_detects_lock_wait_timeout() -> None:
    exc = _build_operational_error(1205, "Lock wait timeout exceeded")
    assert is_retryable_lock_error(exc) is True


def test_is_retryable_lock_error_ignores_other_operational_errors() -> None:
    exc = _build_operational_error(1049, "Unknown database")
    assert is_retryable_lock_error(exc) is False


def test_is_retryable_lock_error_ignores_non_sqlalchemy_errors() -> None:
    assert is_retryable_lock_error(RuntimeError("boom")) is False
