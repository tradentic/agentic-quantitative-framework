from __future__ import annotations

import itertools

import pytest

from utils.guards import SkipStep, retry_on_timeout


def test_retry_on_timeout_retries_timeouts(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    monkeypatch.setattr("utils.guards.time.sleep", lambda _: None)

    attempts = itertools.count(1)

    @retry_on_timeout(attempts=3, backoff=0.1)
    def flaky_call() -> str:
        calls.append(next(attempts))
        if len(calls) < 3:
            raise TimeoutError("network timeout")
        return "ok"

    assert flaky_call() == "ok"
    assert len(calls) == 3


def test_retry_on_timeout_does_not_retry_other_errors() -> None:
    calls = []

    @retry_on_timeout(attempts=5, backoff=0.0)
    def explode() -> None:
        calls.append(None)
        raise ValueError("bad response")

    with pytest.raises(ValueError):
        explode()
    assert len(calls) == 1


def test_retry_on_timeout_passes_skipstep_through() -> None:
    @retry_on_timeout(attempts=2, backoff=0.0)
    def skip() -> None:
        raise SkipStep("no data")

    with pytest.raises(SkipStep):
        skip()
