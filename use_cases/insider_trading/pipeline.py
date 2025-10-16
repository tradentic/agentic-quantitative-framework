"""Glue pipeline for the insider trading use case."""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import yaml

from use_cases.base import StrategyUseCase, UseCaseRequest

logger = logging.getLogger(__name__)

ModuleResult = dict[str, Any]
Runner = Callable[["PipelineRuntime", Mapping[str, Any]], ModuleResult]


@dataclass(frozen=True)
class ModuleDefaults:
    """Default enablement and options for a pipeline module."""

    enabled: bool = True
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModuleExecutionConfig:
    """Configuration parsed from the YAML file for a single module entry."""

    name: str
    enabled_override: bool | None = None
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResolvedModuleConfig:
    """Configuration that is ready to be executed by the pipeline."""

    name: str
    enabled: bool
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PipelineConfig:
    """Container for module defaults and mode execution plans."""

    module_defaults: dict[str, ModuleDefaults]
    modes: dict[str, tuple[ModuleExecutionConfig, ...]]

    def modules_for_mode(self, mode: str) -> tuple[ResolvedModuleConfig, ...]:
        """Return the module sequence for the requested mode."""

        if mode not in self.modes:
            raise KeyError(f"Mode '{mode}' is not defined in the pipeline configuration")
        resolved: list[ResolvedModuleConfig] = []
        for entry in self.modes[mode]:
            defaults = self.module_defaults.get(entry.name, ModuleDefaults())
            enabled = defaults.enabled if entry.enabled_override is None else entry.enabled_override
            options = _merge_options(defaults.options, entry.options)
            resolved.append(
                ResolvedModuleConfig(
                    name=entry.name,
                    enabled=enabled,
                    options=options,
                )
            )
        return tuple(resolved)


@dataclass(frozen=True)
class PipelineRuntime:
    """Runtime arguments supplied via the CLI."""

    mode: str
    trade_date: date | None
    date_from: date | None
    date_to: date | None
    symbols: tuple[str, ...] = ()
    mock: bool = False
    fail_fast: bool = True


@dataclass(frozen=True)
class PipelineStep:
    """Executable pipeline step that knows how to run a module."""

    name: str
    description: str
    runner: Runner

    def execute(self, runtime: PipelineRuntime, options: Mapping[str, Any]) -> ModuleResult:
        result = self.runner(runtime, dict(options))
        if not isinstance(result, dict):
            return {"status": "ok", "result": result}
        if "status" not in result:
            result = {**result, "status": "ok"}
        return result


class PipelineExecutionError(RuntimeError):
    """Raised when a module fails during pipeline execution."""


def _merge_options(
    defaults: Mapping[str, Any] | None, overrides: Mapping[str, Any] | None
) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    if defaults:
        merged.update(defaults)
    if overrides:
        merged.update(overrides)
    return merged


def _coerce_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise TypeError(f"Cannot coerce value {value!r} to a date")


def _coerce_symbols(symbols: Sequence[str] | None) -> tuple[str, ...]:
    if not symbols:
        return ()
    normalized = {
        symbol.strip().upper()
        for symbol in symbols
        if symbol and symbol.strip()
    }
    return tuple(sorted(normalized))


def _should_mock(runtime: PipelineRuntime, options: Mapping[str, Any]) -> bool:
    return runtime.mock or bool(options.get("mock"))


def load_pipeline_config(path: str | Path) -> PipelineConfig:
    """Load the pipeline configuration from a YAML file."""

    with Path(path).open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    if not isinstance(raw, dict):
        raise ValueError("Pipeline configuration must be a mapping")
    raw_defaults = raw.get("module_defaults", {})
    if not isinstance(raw_defaults, dict):
        raise ValueError("module_defaults must be a mapping")
    module_defaults: dict[str, ModuleDefaults] = {}
    for name, payload in raw_defaults.items():
        if payload is None:
            module_defaults[name] = ModuleDefaults()
            continue
        if not isinstance(payload, dict):
            raise ValueError(f"module_defaults entry for {name} must be a mapping")
        enabled = payload.get("enabled")
        options = payload.get("options")
        module_defaults[name] = ModuleDefaults(
            enabled=bool(enabled) if enabled is not None else True,
            options=dict(options or {}),
        )
    raw_modes = raw.get("modes", {})
    if not isinstance(raw_modes, dict):
        raise ValueError("modes must be a mapping")
    modes: dict[str, tuple[ModuleExecutionConfig, ...]] = {}
    for mode_name, entries in raw_modes.items():
        if entries is None:
            modes[mode_name] = tuple()
            continue
        if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
            raise ValueError(f"Mode '{mode_name}' must be a sequence of module entries")
        normalized: list[ModuleExecutionConfig] = []
        for entry in entries:
            normalized.append(_normalize_module_entry(entry))
        modes[mode_name] = tuple(normalized)
    return PipelineConfig(module_defaults=module_defaults, modes=modes)


def _normalize_module_entry(entry: Any) -> ModuleExecutionConfig:
    if isinstance(entry, str):
        return ModuleExecutionConfig(name=entry)
    if not isinstance(entry, Mapping):
        raise ValueError("Module entries must be strings or mappings")
    name = entry.get("name") or entry.get("module")
    if not name:
        raise ValueError("Module entries must declare a name")
    enabled = entry.get("enabled")
    options = entry.get("options")
    return ModuleExecutionConfig(
        name=str(name),
        enabled_override=bool(enabled) if enabled is not None else None,
        options=dict(options or {}),
    )


def _resolve_ingest_dates(runtime: PipelineRuntime, options: Mapping[str, Any]) -> tuple[date | None, date | None]:
    explicit_from = _coerce_date(options.get("date_from")) if options.get("date_from") else None
    explicit_to = _coerce_date(options.get("date_to")) if options.get("date_to") else None
    if explicit_from:
        return explicit_from, explicit_to or explicit_from
    if runtime.date_from:
        return runtime.date_from, runtime.date_to or runtime.date_from
    target = runtime.trade_date
    if options.get("days_back") is not None:
        days_back = int(options.get("days_back"))
        if target is None:
            target = date.today()
        start = target - timedelta(days=abs(days_back))
        return start, target
    return target, runtime.date_to or target


def run_sec_ingest(runtime: PipelineRuntime, options: Mapping[str, Any]) -> ModuleResult:
    """Run the SEC Form 4 ingest flow."""

    if _should_mock(runtime, options):
        logger.info("SEC ingest mock enabled; skipping API calls")
        return {"status": "mocked", "reason": "mock enabled"}
    date_from, date_to = _resolve_ingest_dates(runtime, options)
    if date_from is None:
        logger.info("SEC ingest skipped due to missing start date")
        return {"status": "skipped", "reason": "no date available"}
    from flows.ingest_sec_form4 import ingest_form4

    logger.info("Running SEC ingest from %s to %s", date_from, date_to)
    result = ingest_form4(date_from=date_from, date_to=date_to)
    return {
        "status": "ok",
        "date_from": date_from.isoformat(),
        "date_to": (date_to or date_from).isoformat(),
        "filings": result.get("filings", 0),
        "transactions": result.get("transactions", 0),
    }


def run_market_features(runtime: PipelineRuntime, options: Mapping[str, Any]) -> ModuleResult:
    """Compute market microstructure features for the trade date."""

    if _should_mock(runtime, options):
        logger.info("Market feature computation mocked")
        return {"status": "mocked", "reason": "mock enabled", "rows": 0}
    trade_date = _coerce_date(options.get("trade_date")) if options.get("trade_date") else runtime.trade_date
    if trade_date is None:
        logger.info("Market features skipped due to missing trade date")
        return {"status": "skipped", "reason": "no trade date"}
    persist = bool(options.get("persist", False))
    symbols = options.get("symbols")
    symbol_list: Sequence[str] | None
    if symbols:
        if isinstance(symbols, (str, bytes)):
            symbol_list = [str(symbols)]
        else:
            symbol_list = [str(symbol) for symbol in symbols]
    else:
        symbol_list = list(runtime.symbols) if runtime.symbols else None
    from flows.compute_offexchange_features import compute_offexchange_features

    logger.info("Computing market features for %s", trade_date)
    rows = compute_offexchange_features(trade_date=trade_date, symbols=symbol_list, persist=persist)
    return {
        "status": "ok",
        "trade_date": trade_date.isoformat(),
        "rows": len(rows),
        "persisted": persist,
    }


def run_embeddings(runtime: PipelineRuntime, options: Mapping[str, Any]) -> ModuleResult:
    """Refresh embeddings from the Supabase queue."""

    if _should_mock(runtime, options):
        logger.info("Embedding refresh mocked")
        limit = int(options.get("limit", 0) or 0)
        return {"status": "mocked", "reason": "mock enabled", "limit": limit}
    limit = int(options.get("limit", 5) or 5)
    from flows.embedding_flow import supabase_embedding_refresh

    logger.info("Refreshing embeddings with limit=%d", limit)
    jobs = supabase_embedding_refresh(limit=limit)
    return {"status": "ok", "processed_jobs": len(jobs)}


def run_fingerprints(runtime: PipelineRuntime, options: Mapping[str, Any]) -> ModuleResult:
    """Placeholder fingerprint generation step."""

    fingerprint_size = int(options.get("fingerprint_size", 256) or 256)
    logger.info(
        "Generating (mocked) fingerprints at dimension %d for %s",
        fingerprint_size,
        runtime.trade_date,
    )
    return {
        "status": "ok",
        "fingerprint_size": fingerprint_size,
        "note": "Placeholder implementation; integrate real fingerprint flow here.",
    }


def run_scans(runtime: PipelineRuntime, options: Mapping[str, Any]) -> ModuleResult:
    """Placeholder similarity scan step."""

    if _should_mock(runtime, options):
        logger.info("Similarity scans mocked")
        return {"status": "mocked", "reason": "mock enabled", "top_k": options.get("top_k", 10)}
    top_k = int(options.get("top_k", 10) or 10)
    logger.info("Running placeholder similarity scan with top_k=%d", top_k)
    return {
        "status": "ok",
        "top_k": top_k,
        "note": "Placeholder similarity scan; integrate vector search when available.",
    }


def run_backtest(runtime: PipelineRuntime, options: Mapping[str, Any]) -> ModuleResult:
    """Execute pending backtests."""

    if _should_mock(runtime, options):
        logger.info("Backtest execution mocked")
        return {"status": "mocked", "reason": "mock enabled"}
    limit = int(options.get("limit", 5) or 5)
    from flows.backtest_flow import scheduled_backtest_runner

    logger.info("Executing backtests with limit=%d", limit)
    requests = scheduled_backtest_runner(limit=limit)
    return {"status": "ok", "completed": len(requests)}


MODULE_REGISTRY: dict[str, PipelineStep] = {
    "sec_ingest": PipelineStep(
        name="sec_ingest",
        description="Ingest SEC Form 4 filings",
        runner=run_sec_ingest,
    ),
    "market_features": PipelineStep(
        name="market_features",
        description="Compute market structure features",
        runner=run_market_features,
    ),
    "embeddings": PipelineStep(
        name="embeddings",
        description="Refresh embeddings from Supabase",
        runner=run_embeddings,
    ),
    "fingerprints": PipelineStep(
        name="fingerprints",
        description="Generate signal fingerprints",
        runner=run_fingerprints,
    ),
    "scans": PipelineStep(
        name="scans",
        description="Run similarity scans",
        runner=run_scans,
    ),
    "backtest": PipelineStep(
        name="backtest",
        description="Execute backtests",
        runner=run_backtest,
    ),
}


@dataclass
class InsiderTradingPipeline:
    """End-to-end orchestration for the insider trading use case."""

    config: PipelineConfig
    registry: Mapping[str, PipelineStep] = field(default_factory=lambda: MODULE_REGISTRY)

    def run(self, runtime: PipelineRuntime) -> dict[str, ModuleResult]:
        logger.info(
            "Starting insider trading pipeline mode=%s trade_date=%s", runtime.mode, runtime.trade_date
        )
        modules = self.config.modules_for_mode(runtime.mode)
        results: dict[str, ModuleResult] = {}
        for module_config in modules:
            step = self.registry.get(module_config.name)
            if step is None:
                error = PipelineExecutionError(
                    f"Module '{module_config.name}' is not registered in the pipeline registry"
                )
                if runtime.fail_fast:
                    raise error
                results[module_config.name] = {"status": "error", "error": str(error)}
                continue
            if not module_config.enabled:
                logger.info("Module %s disabled via configuration", module_config.name)
                results[module_config.name] = {
                    "status": "skipped",
                    "reason": "disabled by configuration",
                }
                continue
            try:
                results[module_config.name] = step.execute(runtime, module_config.options)
            except Exception as exc:  # pragma: no cover - logging path
                logger.exception("Module %s failed during execution", module_config.name)
                results[module_config.name] = {"status": "error", "error": str(exc)}
                if runtime.fail_fast:
                    raise PipelineExecutionError(str(exc)) from exc
        return results


# ----------------------------------------------------------------------------
# Legacy agent use case wiring (retained for compatibility)
# ----------------------------------------------------------------------------


@dataclass
class InsiderTradingUseCase(StrategyUseCase):
    """Agent wiring for insider trading anomaly detection."""

    name: str = "insider_trading"
    description: str = (
        "Detect anomalous trades around insider filings using Supabase-backed agents."
    )

    def build_request(self, **kwargs: Any) -> UseCaseRequest:
        symbol = str(kwargs.get("symbol", "")).strip()
        hypothesis = str(kwargs.get("hypothesis", "")).strip()
        feature_candidates = kwargs.get("feature_candidates") or []
        backtest_window = kwargs.get("backtest_window") or {}

        if not symbol:
            raise ValueError("`symbol` is required for the insider trading use case.")
        if not hypothesis:
            raise ValueError("`hypothesis` is required to describe the feature context.")

        payload = {
            "name": f"{symbol}-insider-anomaly",
            "description": hypothesis,
            "metadata": {
                "symbol": symbol,
                "feature_candidates": feature_candidates,
                "backtest_window": backtest_window,
            },
        }
        return UseCaseRequest(intent="propose_new_feature", payload=payload)


# ----------------------------------------------------------------------------
# CLI helpers
# ----------------------------------------------------------------------------


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Insider trading pipeline")
    parser.add_argument(
        "--mode",
        required=True,
        choices=["train", "score", "refresh"],
        help="Pipeline mode to execute",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=str(Path(__file__).with_name("config.yaml")),
        help="Path to the pipeline YAML configuration",
    )
    parser.add_argument("--date", type=str, help="Primary trade date (YYYY-MM-DD)")
    parser.add_argument("--date-from", dest="date_from", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--date-to", dest="date_to", type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--symbol",
        dest="symbols",
        action="append",
        help="Symbols to focus on (can be provided multiple times)",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Enable mock mode to bypass external vendor calls",
    )
    parser.add_argument(
        "--no-fail-fast",
        action="store_true",
        help="Continue executing modules even if one fails",
    )
    return parser.parse_args(argv)


def build_runtime(args: argparse.Namespace) -> PipelineRuntime:
    trade_date = _coerce_date(args.date) if args.date else None
    date_from = _coerce_date(args.date_from) if args.date_from else None
    date_to = _coerce_date(args.date_to) if args.date_to else None
    symbols = _coerce_symbols(args.symbols)
    return PipelineRuntime(
        mode=args.mode,
        trade_date=trade_date,
        date_from=date_from,
        date_to=date_to,
        symbols=symbols,
        mock=bool(args.mock),
        fail_fast=not bool(args.no_fail_fast),
    )


def _json_default(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(f"Object of type {type(value)!r} is not JSON serializable")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = load_pipeline_config(args.config)
    runtime = build_runtime(args)
    pipeline = InsiderTradingPipeline(config=config)
    results = pipeline.run(runtime)
    print(json.dumps(results, default=_json_default, indent=2, sort_keys=True))
    return 0


__all__ = [
    "InsiderTradingPipeline",
    "InsiderTradingUseCase",
    "ModuleDefaults",
    "ModuleExecutionConfig",
    "MODULE_REGISTRY",
    "PipelineConfig",
    "PipelineExecutionError",
    "PipelineRuntime",
    "build_runtime",
    "load_pipeline_config",
    "main",
    "parse_args",
    "ResolvedModuleConfig",
]


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
