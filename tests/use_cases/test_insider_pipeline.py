"""Unit tests for the insider trading pipeline glue code."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Any, Mapping

import pytest

sys.path.append(str(Path(__file__).resolve().parents[2]))

from features.pca_fingerprint import PCA_COMPONENTS
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
    run_fingerprints,
    run_scans,
)
from utils.config import ModuleDefault as ConfigModuleDefault
from utils.config import ModuleEntry as ConfigModuleEntry


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


def test_pipeline_applies_schedule_override() -> None:
    captured: dict[str, Any] = {}

    def runner(runtime: PipelineRuntime, options: Mapping[str, Any]) -> dict[str, Any]:
        captured.update(options)
        return {"status": "ok"}

    base_config = PipelineConfig(
        module_defaults={"alpha": ModuleDefaults(enabled=True, options={"foo": 1})},
        modes={"score": (ModuleExecutionConfig(name="alpha"),)},
    )
    raw_config = {
        "module_defaults": {
            "alpha": ConfigModuleDefault(enabled=True, options={"foo": 1})
        },
        "modes": {
            "score": (ConfigModuleEntry(name="alpha", enabled_override=None, options={}),)
        },
        "schedule_overrides": {
            "2024-01-02": {
                "module_defaults": {
                    "alpha": ConfigModuleDefault(enabled=True, options={"foo": 5})
                },
                "modes": {
                    "score": (
                        ConfigModuleEntry(
                            name="alpha", enabled_override=True, options={"bar": 3}
                        ),
                    )
                },
            }
        },
    }
    pipeline = InsiderTradingPipeline(
        config=base_config,
        registry={
            "alpha": PipelineStep(name="alpha", description="alpha", runner=runner)
        },
        raw_config=raw_config,
    )
    runtime = PipelineRuntime(mode="score", trade_date=date(2024, 1, 2), date_from=None, date_to=None)
    results = pipeline.run(runtime)
    assert results["alpha"]["status"] == "ok"
    assert captured == {"foo": 5, "bar": 3}


def test_run_fingerprints_uses_daily_features(monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import date

    feature_rows = [
        {
            "symbol": "ACME",
            "trade_date": "2024-12-30",
            "short_vol_share": 0.12,
            "short_exempt_share": 0.01,
            "ats_share_of_total": 0.2,
            "provenance": {"source_url": ["http://example.com"]},
        }
    ]

    class _Query:
        def __init__(self, data):
            self._data = data

        def select(self, *_):
            return self

        def eq(self, *_):
            return self

        def in_(self, *_):
            return self

        def execute(self):
            return type("Resp", (), {"data": self._data})()

    class _Client:
        def table(self, name: str):
            assert name == "daily_features"
            return _Query(feature_rows)

    monkeypatch.setattr(
        "use_cases.insider_trading.pipeline.get_supabase_client", lambda: _Client()
    )

    captured: dict[str, Any] = {}

    class _StubFingerprintFlow:
        @staticmethod
        def fn(**kwargs: Any):
            captured.update(kwargs)
            return [
                {
                    "signal_name": kwargs["signal_name"],
                    "asset_symbol": kwargs["asset_symbol"],
                }
            ]

    monkeypatch.setattr(
        "flows.embeddings_and_fingerprints.fingerprint_vectorization",
        _StubFingerprintFlow,
    )

    runtime = PipelineRuntime(
        mode="score",
        trade_date=date(2024, 12, 30),
        date_from=None,
        date_to=None,
        symbols=("ACME",),
    )
    result = run_fingerprints(runtime, {"fingerprint_size": 3})
    assert result["status"] == "ok"
    assert result["fingerprints"] == 1
    assert captured["numeric_features"][0]["window_end"] == "2024-12-30"


def test_run_fingerprints_defaults_to_pca_components(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import date

    feature_rows = [
        {
            "symbol": "ACME",
            "trade_date": "2024-12-30",
            "short_vol_share": 0.12,
            "short_exempt_share": 0.01,
            "ats_share_of_total": 0.2,
            "provenance": {"source_url": ["http://example.com"]},
        }
    ]

    class _Query:
        def __init__(self, data):
            self._data = data

        def select(self, *_):
            return self

        def eq(self, *_):
            return self

        def in_(self, *_):
            return self

        def execute(self):
            return type("Resp", (), {"data": self._data})()

    class _Client:
        def table(self, name: str):
            assert name == "daily_features"
            return _Query(feature_rows)

    monkeypatch.setattr(
        "use_cases.insider_trading.pipeline.get_supabase_client", lambda: _Client()
    )

    captured: dict[str, Any] = {}

    class _StubFingerprintFlow:
        @staticmethod
        def fn(**kwargs: Any):
            captured.update(kwargs)
            return []

    monkeypatch.setattr(
        "flows.embeddings_and_fingerprints.fingerprint_vectorization",
        _StubFingerprintFlow,
    )

    runtime = PipelineRuntime(
        mode="score",
        trade_date=date(2024, 12, 30),
        date_from=None,
        date_to=None,
        symbols=("ACME",),
    )
    result = run_fingerprints(runtime, {})
    assert result["status"] == "ok"
    assert captured["target_dim"] == PCA_COMPONENTS


def test_run_scans_queries_similarity(monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import date

    fingerprint_row = [
        {
            "fingerprint": [0.1, 0.2, 0.3],
            "meta": {"source": "unit"},
            "window_end": "2024-12-30",
        }
    ]

    class _ScanQuery:
        def __init__(self, *args, **kwargs):
            self.symbol = kwargs.get("symbol")
            self.window = kwargs.get("window")
            self.embedding = kwargs.get("embedding")
            self.metadata = kwargs.get("metadata")

    class _Query:
        def __init__(self, data):
            self._data = data

        def select(self, *_):
            return self

        def eq(self, *_):
            return self

        def limit(self, *_):
            return self

        def execute(self):
            return type("Resp", (), {"data": self._data})()

    class _Client:
        def table(self, name: str):
            assert name == "signal_fingerprints"
            return _Query(fingerprint_row)

    monkeypatch.setattr(
        "use_cases.insider_trading.pipeline.get_supabase_client", lambda: _Client()
    )
    monkeypatch.setattr(
        "flows.similarity_scans.SimilarityQuery",
        _ScanQuery,
    )

    class _Match:
        def as_dict(self):
            return {"id": "match-1", "score": 0.9}

    monkeypatch.setattr(
        "flows.similarity_scans.perform_similarity_search",
        lambda query, k: [_Match()],
    )

    runtime = PipelineRuntime(
        mode="score",
        trade_date=date(2024, 12, 30),
        date_from=None,
        date_to=None,
        symbols=("ACME",),
    )
    result = run_scans(runtime, {"top_k": 5})
    assert result["status"] == "ok"
    assert result["results"][0]["matches"][0]["id"] == "match-1"
