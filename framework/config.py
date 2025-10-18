from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Mapping, Sequence

import yaml

DEFAULT_SYMBOL = os.getenv("DEFAULT_SYMBOL", "NVDA").strip() or "NVDA"
DEFAULT_SYMBOL = DEFAULT_SYMBOL.upper()
DEFAULT_ISSUER_CIK = os.getenv("DEFAULT_ISSUER_CIK", "").strip()


@dataclass(frozen=True)
class WatchlistConfig:
    symbols: tuple[str, ...]
    priority_insiders: Mapping[str, tuple[str, ...]]

    def insiders_for(self, symbol: str) -> tuple[str, ...]:
        return tuple(self.priority_insiders.get(symbol.upper(), ()))


@lru_cache(maxsize=1)
def load_watchlist(path: str | Path = Path("configs/watchlist.yaml")) -> WatchlistConfig:
    file_path = Path(path)
    if not file_path.exists():
        return WatchlistConfig(symbols=(DEFAULT_SYMBOL,), priority_insiders={})
    with file_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    raw_symbols: Sequence[str] = tuple(data.get("symbols", []) or [])
    symbols = tuple(symbol.upper() for symbol in raw_symbols) or (DEFAULT_SYMBOL,)
    raw_priority = data.get("priority_insiders", {}) or {}
    priority: dict[str, tuple[str, ...]] = {}
    for key, values in raw_priority.items():
        if isinstance(values, Sequence) and not isinstance(values, (str, bytes)):
            priority[key.upper()] = tuple(str(item) for item in values)
    return WatchlistConfig(symbols=symbols, priority_insiders=priority)


__all__ = ["DEFAULT_SYMBOL", "DEFAULT_ISSUER_CIK", "WatchlistConfig", "load_watchlist"]
