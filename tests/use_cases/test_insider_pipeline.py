"""Unit tests for the insider trading pipeline glue code."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

sys.path.append(str(Path(__file__).resolve().parents[2]))

from use_cases.insider_trading.pipeline import (
    InsiderTradingPipeline,
    ModuleDefaults,
    ModuleExecutionConfig,
    PipelineConfig,
    PipelineExecutionError,
    PipelineRuntime,
    PipelineStep,
    ResolvedModuleConfig,
    load_pipeline_config,
)


def test_load_pipeline_config_merges_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
module_defaults:
  alpha:
    enabled: true
    options:
      foo: 1
modes:
  score:
    - name: alpha
      options:
        bar: 2
""",
        encoding="utf-8",
    )
    config = load_pipeline_config(config_path)
    modules = config.modules_for_mode("score")
    assert modules == (
        ResolvedModuleConfig(name="alpha", enabled=True, options={"foo": 1, "bar": 2}),
    )


def test_pipeline_run_executes_enabled_modules() -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def run_alpha(runtime: PipelineRuntime, options: dict[str, object]) -> dict[str, object]:
        calls.append(("alpha", dict(options)))
        return {"status": "ok", "options": dict(options)}

    def run_beta(runtime: PipelineRuntime, options: dict[str, object]) -> dict[str, object]:
        calls.append(("beta", dict(options)))
        return {"status": "ok"}

    config = PipelineConfig(
        module_defaults={
            "alpha": ModuleDefaults(enabled=True, options={"foo": 1}),
            "beta": ModuleDefaults(enabled=True, options={}),
        },
        modes={
            "score": (
                ModuleExecutionConfig(name="alpha"),
                ModuleExecutionConfig(name="beta", enabled_override=False),
            )
        },
    )
    pipeline = InsiderTradingPipeline(
        config=config,
        registry={
            "alpha": PipelineStep(name="alpha", description="alpha", runner=run_alpha),
            "beta": PipelineStep(name="beta", description="beta", runner=run_beta),
        },
    )
    runtime = PipelineRuntime(mode="score", trade_date=None, date_from=None, date_to=None)
    results = pipeline.run(runtime)
    assert list(results) == ["alpha", "beta"]
    assert results["alpha"]["status"] == "ok"
    assert results["beta"]["status"] == "skipped"
    assert calls == [("alpha", {"foo": 1})]


def test_pipeline_fail_fast(tmp_path: Path) -> None:
    config = PipelineConfig(
        module_defaults={"alpha": ModuleDefaults(enabled=True, options={})},
        modes={"score": (ModuleExecutionConfig(name="alpha"),)},
    )

    def failing(runtime: PipelineRuntime, options: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("boom")

    pipeline = InsiderTradingPipeline(
        config=config,
        registry={"alpha": PipelineStep(name="alpha", description="alpha", runner=failing)},
    )
    runtime = PipelineRuntime(mode="score", trade_date=None, date_from=None, date_to=None)
    with pytest.raises(PipelineExecutionError):
        pipeline.run(runtime)

    runtime_nonfatal = PipelineRuntime(
        mode="score", trade_date=None, date_from=None, date_to=None, fail_fast=False
    )
    results = pipeline.run(runtime_nonfatal)
    assert results["alpha"]["status"] == "error"
    assert "boom" in results["alpha"]["error"]
