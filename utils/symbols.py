"""Utilities for symbol normalization and case coercion."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

__all__ = ["coerce_symbol_case", "normalize_symbol_list"]


def coerce_symbol_case(symbol: Any, *, case: str = "upper") -> str:
    """Return the trimmed symbol coerced to the requested case.

    Parameters
    ----------
    symbol:
        Value to normalize. ``None`` and empty values yield an empty string.
    case:
        Either ``"upper"`` (default) or ``"lower"`` to control casing. Any
        other value raises ``ValueError`` to avoid silent misconfiguration.
    """

    if symbol is None:
        return ""
    normalized = str(symbol).strip()
    if not normalized:
        return ""
    if case == "upper":
        return normalized.upper()
    if case == "lower":
        return normalized.lower()
    raise ValueError(f"Unsupported symbol case '{case}'. Use 'upper' or 'lower'.")


def normalize_symbol_list(
    symbols: Iterable[Any] | None,
    *,
    case: str = "upper",
    unique: bool = True,
    sort: bool = True,
) -> list[str]:
    """Normalize a sequence of symbols.

    Parameters
    ----------
    symbols:
        Iterable of values to normalize. Strings, numbers, and nested iterables
        are all coerced to strings. ``None`` or blank values are skipped.
    case:
        Passed to :func:`coerce_symbol_case`.
    unique:
        When ``True`` (default) duplicates are removed while preserving the
        last encountered casing.
    sort:
        When ``True`` (default) the output symbols are returned in lexicographic
        order. Set to ``False`` to preserve insertion order for non-unique
        sequences.
    """

    if not symbols:
        return []

    seen: set[str] | None
    if unique:
        seen = set()
    else:
        seen = None

    normalized: list[str] = []
    for raw in symbols:
        coerced = coerce_symbol_case(raw, case=case)
        if not coerced:
            continue
        if seen is not None:
            if coerced in seen:
                continue
            seen.add(coerced)
        normalized.append(coerced)

    if sort:
        normalized.sort()
    return normalized
