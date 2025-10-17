"""Configuration helpers for pipeline execution."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Mapping

import yaml

__all__ = ["ConfigError", "get_config_for_date", "load_pipeline_config"]


class ConfigError(ValueError):
    """Raised when a configuration file cannot be parsed."""


@dataclass(frozen=True)
class ModuleEntry:
    """Normalized representation of a module entry."""

    name: str
    enabled_override: bool | None
    options: dict[str, Any]


@dataclass(frozen=True)
class ModuleDefault:
    """Normalized representation of module defaults."""

    enabled: bool | None
    options: dict[str, Any]


def load_pipeline_config(path: str | Path) -> dict[str, Any]:
    """Load and normalize a pipeline configuration YAML file."""

    path = Path(path)
    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    if not isinstance(raw, Mapping):  # pragma: no cover - defensive
        raise ConfigError("Pipeline configuration must be a mapping")
    module_defaults = _normalize_module_defaults(raw.get("module_defaults") or {})
    modes = _normalize_modes(raw.get("modes") or {})
    schedule_overrides = _normalize_schedule_overrides(raw.get("schedule_overrides"))
    normalized: dict[str, Any] = {
        "module_defaults": module_defaults,
        "modes": modes,
    }
    if schedule_overrides:
        normalized["schedule_overrides"] = schedule_overrides
    return normalized


def get_config_for_date(
    config: Mapping[str, Any],
    *,
    trade_date: date | None = None,
) -> dict[str, Any]:
    """Return configuration after applying schedule overrides for ``trade_date``."""

    resolved = {
        "module_defaults": deepcopy(config.get("module_defaults", {})),
        "modes": deepcopy(config.get("modes", {})),
    }
    if not trade_date:
        return resolved
    overrides = config.get("schedule_overrides") or {}
    if not overrides:
        return resolved
    override = _find_override(overrides, trade_date)
    if override:
        resolved = _apply_override(resolved, override)
    return resolved


def _normalize_module_defaults(
    payload: Mapping[str, Any], *, allow_partial: bool = False
) -> dict[str, ModuleDefault]:
    defaults: dict[str, ModuleDefault] = {}
    for name, value in payload.items():
        if value is None:
            defaults[str(name)] = ModuleDefault(
                enabled=None if allow_partial else True, options={}
            )
            continue
        if not isinstance(value, Mapping):
            raise ConfigError(f"module_defaults entry for '{name}' must be a mapping")
        enabled = value.get("enabled")
        options = value.get("options")
        normalized_enabled: bool | None
        if allow_partial:
            normalized_enabled = bool(enabled) if enabled is not None else None
        else:
            normalized_enabled = bool(enabled) if enabled is not None else True
        defaults[str(name)] = ModuleDefault(
            enabled=normalized_enabled,
            options=dict(options or {}),
        )
    return defaults


def _normalize_modes(payload: Mapping[str, Any]) -> dict[str, tuple[ModuleEntry, ...]]:
    modes: dict[str, tuple[ModuleEntry, ...]] = {}
    for mode, entries in payload.items():
        if entries is None:
            modes[str(mode)] = tuple()
            continue
        if not isinstance(entries, list):
            raise ConfigError(f"Mode '{mode}' must be a list of module entries")
        normalized_entries: list[ModuleEntry] = []
        for entry in entries:
            normalized_entries.append(_normalize_module_entry(entry))
        modes[str(mode)] = tuple(normalized_entries)
    return modes


def _normalize_module_entry(entry: Any) -> ModuleEntry:
    if isinstance(entry, str):
        return ModuleEntry(name=entry, enabled_override=None, options={})
    if not isinstance(entry, Mapping):
        raise ConfigError("Module entries must be strings or mappings")
    name = entry.get("name") or entry.get("module")
    if not name:
        raise ConfigError("Module entries must declare a name")
    enabled = entry.get("enabled")
    options = entry.get("options")
    return ModuleEntry(
        name=str(name),
        enabled_override=bool(enabled) if enabled is not None else None,
        options=dict(options or {}),
    )


def _normalize_schedule_overrides(payload: Any) -> dict[str, dict[str, Any]]:
    if not payload:
        return {}
    if not isinstance(payload, Mapping):
        raise ConfigError("schedule_overrides must be a mapping")
    overrides: dict[str, dict[str, Any]] = {}
    for key, value in payload.items():
        if not isinstance(value, Mapping):
            raise ConfigError("schedule override entries must be mappings")
        overrides[str(key)] = {
            "module_defaults": _normalize_module_defaults(
                value.get("module_defaults") or {}, allow_partial=True
            ),
            "modes": _normalize_modes(value.get("modes") or {}),
        }
    return overrides


def _find_override(overrides: Mapping[str, dict[str, Any]], target: date) -> dict[str, Any] | None:
    iso_key = target.isoformat()
    if iso_key in overrides:
        return overrides[iso_key]
    weekday_key = f"weekday:{target.weekday()}"
    return overrides.get(weekday_key)


def _apply_override(
    base: dict[str, Any], override: Mapping[str, Any]
) -> dict[str, Any]:
    resolved = deepcopy(base)
    for name, default in (override.get("module_defaults") or {}).items():
        existing: ModuleDefault | dict[str, Any] | None = resolved["module_defaults"].get(name)
        if isinstance(existing, ModuleDefault):
            enabled = existing.enabled
            if default.enabled is not None:
                enabled = default.enabled
            options = dict(existing.options)
            options.update(default.options)
            resolved["module_defaults"][name] = ModuleDefault(enabled=enabled, options=options)
        else:
            resolved["module_defaults"][name] = ModuleDefault(
                enabled=default.enabled if default.enabled is not None else True,
                options=dict(default.options),
            )
    for mode, entries in (override.get("modes") or {}).items():
        resolved["modes"][mode] = entries
    return resolved
