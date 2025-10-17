from __future__ import annotations

import logging
from datetime import date

import pytest

from use_cases.insider_trading.pipeline import (
    InsiderTradingPipeline,
    ModuleExecutionConfig,
    PipelineConfig,
    PipelineRuntime,
    PipelineStep,
)
from utils.guards import SkipStep


@pytest.fixture
def runtime() -> PipelineRuntime:
    return PipelineRuntime(
        mode="train",
        trade_date=date.today(),
        date_from=None,
        date_to=None,
        symbols=(),
        mock=False,
        fail_fast=True,
    )


def test_pipeline_skips_step_on_skipstep(caplog: pytest.LogCaptureFixture, runtime: PipelineRuntime) -> None:
    config = PipelineConfig(
        module_defaults={},
        modes={
            "train": (
                ModuleExecutionConfig(name="skip"),
                ModuleExecutionConfig(name="ok"),
            )
        },
    )

    def _skip_runner(*_, **__) -> dict[str, str]:
        raise SkipStep("no symbols")

    def _ok_runner(*_, **__) -> dict[str, str]:
        return {"detail": "executed"}

    registry = {
        "skip": PipelineStep(name="skip", description="skip", runner=_skip_runner),
        "ok": PipelineStep(name="ok", description="ok", runner=_ok_runner),
    }

    pipeline = InsiderTradingPipeline(config=config, registry=registry)

    caplog.set_level(logging.INFO)
    results = pipeline.run(runtime)

    assert results["skip"] == {"status": "skipped", "reason": "no symbols"}
    assert results["ok"]["status"] == "ok"
    assert any("Module skip skipped: no symbols" in message for message in caplog.messages)
