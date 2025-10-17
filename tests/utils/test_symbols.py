from __future__ import annotations

import pytest

from utils.symbols import coerce_symbol_case, normalize_symbol_list


def test_normalize_symbol_list_deduplicates_and_sorts() -> None:
    symbols = [" aapl ", "MSFT", "aapl", None, "", "gOoG"]
    assert normalize_symbol_list(symbols) == ["AAPL", "GOOG", "MSFT"]


def test_normalize_symbol_list_preserves_order_when_requested() -> None:
    symbols = ["msft", "aapl", "msft"]
    assert normalize_symbol_list(symbols, sort=False) == ["MSFT", "AAPL"]


def test_normalize_symbol_list_with_duplicates_when_unique_disabled() -> None:
    symbols = ["aapl", "aapl", "msft"]
    assert normalize_symbol_list(symbols, unique=False) == ["AAPL", "AAPL", "MSFT"]


def test_normalize_symbol_list_lowercase() -> None:
    assert normalize_symbol_list(["AAPL", " Msft"], case="lower") == ["aapl", "msft"]


def test_coerce_symbol_case_handles_invalid_case() -> None:
    with pytest.raises(ValueError):
        coerce_symbol_case("AAPL", case="title")


def test_coerce_symbol_case_trims_and_coerces() -> None:
    assert coerce_symbol_case("  aapl  ") == "AAPL"
    assert coerce_symbol_case("MsFt", case="lower") == "msft"
