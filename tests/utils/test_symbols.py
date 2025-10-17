"""Unit tests for the symbol normalization helpers."""

from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))

from utils.symbols import coerce_symbol_case, normalize_symbol_list


def test_coerce_symbol_case_handles_none_and_whitespace() -> None:
    assert coerce_symbol_case(None) == ""
    assert coerce_symbol_case("  ") == ""
    assert coerce_symbol_case("msft") == "MSFT"
    assert coerce_symbol_case("msft", uppercase=False) == "msft"


def test_normalize_symbol_list_filters_and_sorts() -> None:
    symbols = [" msft", "AAPL", "", None, "msft", "Goog"]
    normalized = normalize_symbol_list(symbols)
    assert normalized == ["AAPL", "GOOG", "MSFT"]


def test_normalize_symbol_list_preserves_order_when_requested() -> None:
    symbols = ["msft", "AAPL", "msft", "GOOG"]
    normalized = normalize_symbol_list(symbols, unique=True, sort=False)
    assert normalized == ["MSFT", "AAPL", "GOOG"]
    repeated = normalize_symbol_list(symbols, unique=False, sort=False)
    assert repeated == ["MSFT", "AAPL", "MSFT", "GOOG"]
