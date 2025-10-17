"""Utilities for working with equity symbols across the codebase."""

from __future__ import annotations

from collections.abc import Iterable


def coerce_symbol_case(symbol: object | None, *, uppercase: bool = True) -> str:
    """Return the normalized symbol string or an empty string if invalid.

    Parameters
    ----------
    symbol:
        Any object that can be coerced to a string. ``None`` and empty strings
        are treated as missing values.
    uppercase:
        When ``True`` (the default) the symbol will be upper-cased. When
        ``False`` the symbol is returned in lower-case.
    """

    if symbol is None:
        return ""
    text = str(symbol).strip()
    if not text:
        return ""
    return text.upper() if uppercase else text.lower()


def normalize_symbol_list(
    symbols: Iterable[object] | None,
    *,
    uppercase: bool = True,
    unique: bool = True,
    sort: bool = True,
) -> list[str]:
    """Normalize a sequence of symbols, filtering blanks and enforcing casing.

    Parameters
    ----------
    symbols:
        Iterable of raw symbol inputs. ``None`` yields an empty list.
    uppercase:
        When ``True`` (default) the returned symbols are upper-cased.
    unique:
        When ``True`` (default) duplicates are removed.
    sort:
        When ``True`` (default) the result is sorted alphabetically. Sorting is
        only applied when ``unique`` is also ``True``.
    """

    if not symbols:
        return []

    normalized = [coerce_symbol_case(symbol, uppercase=uppercase) for symbol in symbols]
    filtered = [symbol for symbol in normalized if symbol]

    if not unique:
        return filtered

    if sort:
        return sorted(set(filtered))

    seen: set[str] = set()
    ordered: list[str] = []
    for symbol in filtered:
        if symbol not in seen:
            seen.add(symbol)
            ordered.append(symbol)
    return ordered


__all__ = ["coerce_symbol_case", "normalize_symbol_list"]

