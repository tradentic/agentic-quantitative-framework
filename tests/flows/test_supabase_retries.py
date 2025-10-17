"""Tests for Supabase retry and guard helpers."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.guards import SkipStep, retry_on_timeout


class _DummyTimeout(TimeoutError):
    """Sentinel timeout exception for retry validation."""


def test_retry_on_timeout_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []
    monkeypatch.setattr(time, "sleep", lambda *_: None)

    @retry_on_timeout(attempts=3, backoff=0.0, jitter=0.0)
    def _fetch() -> str:
        calls.append(len(calls))
        if len(calls) < 3:
            raise _DummyTimeout("timeout")
        return "ok"

    assert _fetch() == "ok"
    assert len(calls) == 3


def test_retry_on_timeout_does_not_mask_non_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []
    monkeypatch.setattr(time, "sleep", lambda *_: None)

    @retry_on_timeout(attempts=4, backoff=0.0, jitter=0.0)
    def _fail() -> None:
        calls.append(len(calls))
        raise ValueError("boom")

    with pytest.raises(ValueError):
        _fail()
    assert calls == [0]


def test_retry_on_timeout_propagates_skipstep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(time, "sleep", lambda *_: None)

    @retry_on_timeout(attempts=5, backoff=0.0, jitter=0.0)
    def _skip() -> None:
        raise SkipStep("No symbols")

    with pytest.raises(SkipStep):
        _skip()
