"""Regression tests for the shared configuration helpers."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from utils.config import (
    PipelineConfig,
    ResolvedModuleConfig,
    get_config_for_date,
    load_pipeline_config,
)


def test_load_pipeline_config_parses_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "pipeline.yaml"
    config_path.write_text(
        """
module_defaults:
  alpha:
    enabled: true
    options:
      foo: 1
  beta:
    enabled: false
    options:
      foo: 2
modes:
  score:
    - name: alpha
    - name: beta
      enabled: true
      options:
        bar: 3
""",
        encoding="utf-8",
    )

    config = load_pipeline_config(config_path)
    assert isinstance(config, PipelineConfig)
    modules = config.modules_for_mode("score")
    assert modules == (
        ResolvedModuleConfig(name="alpha", enabled=True, options={"foo": 1}),
        ResolvedModuleConfig(name="beta", enabled=True, options={"foo": 2, "bar": 3}),
    )


def test_get_config_for_date_supports_overrides(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
fingerprints:
  defaults:
    window_days: 7
    signal_name: base
  overrides:
    "2024-12-24":
      window_days: 5
      signal_name: holiday
""",
        encoding="utf-8",
    )

    defaults = get_config_for_date("fingerprints", date(2024, 12, 23), config_path=config_path)
    assert defaults == {"window_days": 7, "signal_name": "base"}

    override = get_config_for_date("fingerprints", date(2024, 12, 24), config_path=config_path)
    assert override == {"window_days": 5, "signal_name": "holiday"}


def test_get_config_for_date_accepts_preloaded_mapping() -> None:
    config = {
        "scans": {
            "defaults": {"top_k": 10},
            "overrides": {"2024-01-01": {"top_k": 5}},
        }
    }

    defaults = get_config_for_date("scans", None, config=config)
    assert defaults == {"top_k": 10}

    override = get_config_for_date("scans", date(2024, 1, 1), config=config)
    assert override == {"top_k": 5}
