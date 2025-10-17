"""Pipeline SkipStep handling tests."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from use_cases.insider_trading.pipeline import (
    InsiderTradingPipeline,
    ModuleDefaults,
    ModuleExecutionConfig,
    PipelineConfig,
    PipelineRuntime,
    PipelineStep,
)
from utils.guards import SkipStep


def test_pipeline_logs_and_skips_modules(caplog: pytest.LogCaptureFixture) -> None:
    triggered: list[str] = []

    def _skip_runner(*_: object, **__: object) -> dict[str, str]:
        raise SkipStep("No symbols")

    def _ok_runner(*_: object, **__: object) -> dict[str, str]:
        triggered.append("ok")
        return {"status": "ok", "result": "ran"}

    config = PipelineConfig(
        module_defaults={"skip": ModuleDefaults(), "ok": ModuleDefaults()},
        modes={
            "score": (
                ModuleExecutionConfig(name="skip"),
                ModuleExecutionConfig(name="ok"),
            )
        },
    )
    pipeline = InsiderTradingPipeline(
        config=config,
        registry={
            "skip": PipelineStep(name="skip", description="Skip", runner=_skip_runner),
            "ok": PipelineStep(name="ok", description="OK", runner=_ok_runner),
        },
    )
    runtime = PipelineRuntime(mode="score", trade_date=None, date_from=None, date_to=None)

    with caplog.at_level(logging.INFO):
        results = pipeline.run(runtime)

    assert results["skip"] == {"status": "skipped", "reason": "No symbols"}
    assert results["ok"]["status"] == "ok"
    assert triggered == ["ok"]
    assert any("No symbols" in record.message for record in caplog.records)
