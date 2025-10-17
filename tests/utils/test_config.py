from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from utils.config import ConfigError, get_config_for_date, load_pipeline_config


def test_load_pipeline_config_normalizes_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
module_defaults:
  alpha:
    enabled: false
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
    default = config["module_defaults"]["alpha"]
    assert default.enabled is False
    assert default.options == {"foo": 1}
    entries = config["modes"]["score"]
    assert len(entries) == 1
    assert entries[0].name == "alpha"
    assert entries[0].options == {"bar": 2}


def test_get_config_for_date_applies_specific_override(tmp_path: Path) -> None:
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
schedule_overrides:
  2024-01-10:
    module_defaults:
      alpha:
        options:
          foo: 5
    modes:
      score:
        - name: alpha
          enabled: false
""",
        encoding="utf-8",
    )
    config = load_pipeline_config(config_path)
    resolved = get_config_for_date(config, trade_date=date(2024, 1, 10))
    default = resolved["module_defaults"]["alpha"]
    assert default.enabled is True
    assert default.options == {"foo": 5}
    mode_entries = resolved["modes"]["score"]
    assert len(mode_entries) == 1
    assert mode_entries[0].enabled_override is False


def test_get_config_for_date_uses_weekday_override(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
module_defaults:
  alpha:
    enabled: true
    options:
      foo: 1
schedule_overrides:
  weekday:2:
    module_defaults:
      alpha:
        options:
          foo: 7
""",
        encoding="utf-8",
    )
    config = load_pipeline_config(config_path)
    resolved = get_config_for_date(config, trade_date=date(2024, 1, 3))
    default = resolved["module_defaults"]["alpha"]
    assert default.options == {"foo": 7}


def test_load_pipeline_config_validates_mapping(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("[]", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_pipeline_config(config_path)
