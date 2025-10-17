"""Helper utilities for flow control and Supabase resilience."""

from __future__ import annotations

import logging
import os
import random
import time
from functools import wraps
from typing import Callable, Iterable, ParamSpec, TypeVar


logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")

DEFAULT_TIMEOUT_ATTEMPTS = int(os.getenv("SUPABASE_TIMEOUT_ATTEMPTS", "3"))
DEFAULT_TIMEOUT_BACKOFF = float(os.getenv("SUPABASE_TIMEOUT_BACKOFF", "0.5"))
DEFAULT_TIMEOUT_JITTER = float(os.getenv("SUPABASE_TIMEOUT_JITTER", "0.05"))


def _collect_timeout_exceptions() -> tuple[type[BaseException], ...]:
    """Aggregate known timeout exception classes from optional clients."""

    candidates: list[type[BaseException]] = [TimeoutError]
    try:  # pragma: no cover - optional dependency
        import socket

        candidates.append(socket.timeout)
    except Exception:  # pragma: no cover - optional dependency missing
        pass
    try:  # pragma: no cover - optional dependency
        from requests import exceptions as requests_exceptions

        candidates.append(requests_exceptions.Timeout)
    except Exception:
        pass
    try:  # pragma: no cover - optional dependency
        import httpx

        candidates.extend([httpx.ReadTimeout, httpx.ConnectTimeout])
    except Exception:
        pass
    try:  # pragma: no cover - optional dependency
        import urllib3

        candidates.append(urllib3.exceptions.ReadTimeoutError)
    except Exception:
        pass

    unique: dict[str, type[BaseException]] = {}
    for exc in candidates:
        unique[f"{exc.__module__}.{exc.__qualname__}"] = exc
    return tuple(unique.values())


TIMEOUT_ERRORS = _collect_timeout_exceptions()


class SkipStep(RuntimeError):
    """Raised by flows when a step should be skipped without failing the pipeline."""


def retry_on_timeout(
    func: Callable[P, R] | None = None,
    *,
    attempts: int = DEFAULT_TIMEOUT_ATTEMPTS,
    backoff: float = DEFAULT_TIMEOUT_BACKOFF,
    jitter: float = DEFAULT_TIMEOUT_JITTER,
) -> Callable[[Callable[P, R]], Callable[P, R]] | Callable[P, R]:
    """Retry decorated callables on timeout errors with exponential backoff."""

    def decorator(target: Callable[P, R]) -> Callable[P, R]:
        max_attempts = max(int(attempts), 1)
        base_backoff = max(float(backoff), 0.0)
        jitter_amount = max(float(jitter), 0.0)

        @wraps(target)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            delay = base_backoff
            for attempt_idx in range(1, max_attempts + 1):
                try:
                    return target(*args, **kwargs)
                except SkipStep:
                    raise
                except TIMEOUT_ERRORS as exc:
                    if attempt_idx >= max_attempts:
                        logger.warning(
                            "Supabase call %s exhausted %d timeout retries", target.__name__, max_attempts
                        )
                        raise
                    sleep_for = delay
                    if jitter_amount:
                        sleep_for += random.uniform(-jitter_amount, jitter_amount)
                        sleep_for = max(sleep_for, 0.0)
                    logger.warning(
                        "Supabase call %s timed out (attempt %d/%d): %s",
                        target.__name__,
                        attempt_idx,
                        max_attempts,
                        exc,
                    )
                    if sleep_for:
                        time.sleep(sleep_for)
                    delay = delay * 2 if delay else base_backoff or 0.0
                except Exception:
                    raise
            raise RuntimeError("Retry wrapper exhausted without executing target function.")

        return wrapper

    if func is not None:
        return decorator(func)
    return decorator


def ensure_not_empty(frame: Iterable[object] | object, label: str = "dataset") -> object:
    """Ensure an iterable/pandas-like frame is not empty, raising :class:`SkipStep`."""

    if frame is None:
        raise SkipStep(f"{label} is empty")

    is_empty = False
    if hasattr(frame, "empty"):
        try:
            is_empty = bool(getattr(frame, "empty"))
        except Exception:  # pragma: no cover - defensive guard
            is_empty = False
    if not is_empty and hasattr(frame, "__len__"):
        try:
            is_empty = len(frame) == 0  # type: ignore[arg-type]
        except TypeError:  # pragma: no cover - defensive guard
            is_empty = False
    if is_empty:
        raise SkipStep(f"{label} is empty")
    return frame


__all__ = ["retry_on_timeout", "ensure_not_empty", "SkipStep"]
