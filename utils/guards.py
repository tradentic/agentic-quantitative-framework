"""Guard utilities shared across flows and pipelines."""

from __future__ import annotations

import logging
import time
from functools import wraps
from typing import Callable, ParamSpec, TypeVar

try:  # pragma: no cover - optional dependency
    import httpx
except ModuleNotFoundError:  # pragma: no cover - fallback when httpx missing
    httpx = None  # type: ignore[assignment]


LOGGER = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


class SkipStep(RuntimeError):
    """Raised when a pipeline step should be skipped without failing the run."""


def _timeout_exceptions() -> tuple[type[BaseException], ...]:
    base: tuple[type[BaseException], ...] = (TimeoutError,)
    if httpx is not None:  # pragma: no cover - exercised when httpx installed
        return base + (httpx.TimeoutException,)
    return base


TIMEOUT_EXCEPTIONS = _timeout_exceptions()


def retry_on_timeout(*, attempts: int = 3, backoff: float = 0.5) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Retry Supabase interactions when they raise timeout errors."""

    attempts = max(int(attempts), 1)
    backoff = max(float(backoff), 0.0)

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            delay = backoff
            last_error: BaseException | None = None
            for attempt in range(1, attempts + 1):
                try:
                    return func(*args, **kwargs)
                except SkipStep:
                    raise
                except TIMEOUT_EXCEPTIONS as exc:
                    last_error = exc
                    if attempt >= attempts:
                        raise
                    LOGGER.warning(
                        "Supabase call %s timed out (attempt %d/%d); retrying in %.2fs",
                        func.__name__,
                        attempt,
                        attempts,
                        delay,
                    )
                    if delay:
                        time.sleep(delay)
                        delay *= 2
                except Exception:
                    raise
            if last_error is not None:  # pragma: no cover - defensive guard
                raise last_error
            raise RuntimeError("retry_on_timeout exhausted without executing target function.")

        return wrapper

    return decorator


def ensure_not_empty(frame, label: str):
    """Ensure a pandas DataFrame-like object is not empty, otherwise skip the step."""

    is_empty = getattr(frame, "empty", None)
    if is_empty is None:
        raise TypeError(f"{label} must provide an 'empty' attribute for emptiness checks.")
    if is_empty:
        raise SkipStep(f"{label} is empty")
    return frame


__all__ = ["SkipStep", "ensure_not_empty", "retry_on_timeout"]
