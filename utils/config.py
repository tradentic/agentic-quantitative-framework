"""Configuration helpers shared across pipelines and feature modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Sequence

import yaml


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
            enabled = (
                defaults.enabled if entry.enabled_override is None else entry.enabled_override
            )
            options = _merge_options(defaults.options, entry.options)
            resolved.append(
                ResolvedModuleConfig(
                    name=entry.name,
                    enabled=enabled,
                    options=options,
                )
            )
        return tuple(resolved)


def _merge_options(
    defaults: Mapping[str, Any] | None, overrides: Mapping[str, Any] | None
) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    if defaults:
        merged.update(defaults)
    if overrides:
        merged.update(overrides)
    return merged


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


def load_pipeline_config(path: str | Path) -> PipelineConfig:
    """Load the pipeline configuration from a YAML file."""

    raw = _load_yaml(Path(path))
    if not isinstance(raw, Mapping):
        raise ValueError("Pipeline configuration must be a mapping")

    raw_defaults = raw.get("module_defaults", {})
    if not isinstance(raw_defaults, Mapping):
        raise ValueError("module_defaults must be a mapping")
    module_defaults: dict[str, ModuleDefaults] = {}
    for name, payload in raw_defaults.items():
        if payload is None:
            module_defaults[name] = ModuleDefaults()
            continue
        if not isinstance(payload, Mapping):
            raise ValueError(f"module_defaults entry for {name} must be a mapping")
        enabled = payload.get("enabled")
        options = payload.get("options")
        module_defaults[name] = ModuleDefaults(
            enabled=bool(enabled) if enabled is not None else True,
            options=dict(options or {}),
        )

    raw_modes = raw.get("modes", {})
    if not isinstance(raw_modes, Mapping):
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


def _load_yaml(path: Path) -> MutableMapping[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        content = yaml.safe_load(handle) or {}
    if not isinstance(content, MutableMapping):
        raise ValueError(f"Configuration file {path} must contain a mapping at the root")
    return content


def _default_app_config_path() -> Path:
    return Path("config.yaml")


@lru_cache(maxsize=8)
def _load_app_config(path: Path | None = None) -> Mapping[str, Any]:
    config_path = path or _default_app_config_path()
    if not config_path.exists():
        return {}
    raw = _load_yaml(config_path)
    return dict(raw)


def get_config_for_date(
    section: str,
    trade_date: date | None,
    *,
    config: Mapping[str, Any] | None = None,
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    """Return configuration defaults merged with date-specific overrides.

    Parameters
    ----------
    section:
        Top-level key within the configuration file.
    trade_date:
        Date whose overrides should be applied. ``None`` will skip overrides.
    config:
        Pre-loaded configuration mapping. When supplied, the configuration file
        is not re-read. ``config_path`` is ignored when ``config`` is provided.
    config_path:
        Optional path to the configuration file. Defaults to ``config.yaml`` at
        the repository root.
    """

    if config is None:
        resolved_path = Path(config_path) if config_path is not None else None
        config = _load_app_config(resolved_path)

    section_payload = config.get(section, {}) if config else {}
    if not isinstance(section_payload, Mapping):
        raise ValueError(f"Section '{section}' must be a mapping in the configuration")

    defaults = dict(section_payload.get("defaults") or {})
    overrides = section_payload.get("overrides") or {}

    if trade_date is None or not overrides:
        return defaults

    if not isinstance(overrides, Mapping):
        raise ValueError(f"Overrides for section '{section}' must be a mapping")

    key = trade_date.isoformat()
    override_payload = overrides.get(key)
    if override_payload and isinstance(override_payload, Mapping):
        defaults.update(override_payload)
    return defaults


__all__ = [
    "ModuleDefaults",
    "ModuleExecutionConfig",
    "PipelineConfig",
    "ResolvedModuleConfig",
    "get_config_for_date",
    "load_pipeline_config",
]

