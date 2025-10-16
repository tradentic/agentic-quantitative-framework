from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))

import pytest

from framework.vendor_markets import (
    DEFAULT_VENDOR_ENV_VAR,
    PolygonMarketDataClient,
    create_market_data_client,
)


class DummyResponse:
    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict[str, Any]:
        return self._payload


class DummySession:
    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        self.payloads = payloads
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, params: dict[str, Any] | None = None, timeout: float | None = None) -> DummyResponse:
        if not self.payloads:
            raise AssertionError("No payloads remaining for request")
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        return DummyResponse(self.payloads.pop(0))


@pytest.fixture()
def polygon_sample_payloads() -> list[dict[str, Any]]:
    trade_payload = {
        "results": [
            {
                "sip_timestamp": 1,
                "price": 189.12,
                "size": 100,
                "exchange": 11,
                "conditions": [14, 37],
                "sequence_number": 1,
                "participant_timestamp": 2,
                "trf_timestamp": None,
                "tape": 1,
                "id": "T1",
                "trf_id": None,
            }
        ],
        "next_url": None,
    }
    quote_payload = {
        "results": [
            {
                "sip_timestamp": 5,
                "bid_price": 189.1,
                "bid_size": 200,
                "ask_price": 189.2,
                "ask_size": 100,
                "bid_exchange": 11,
                "ask_exchange": 12,
                "conditions": [1],
                "sequence_number": 2,
                "participant_timestamp": 6,
                "trf_timestamp": None,
                "tape": 1,
            }
        ],
        "next_url": None,
    }
    return [trade_payload, quote_payload]


def test_polygon_trades_and_quotes_are_normalized(polygon_sample_payloads: list[dict[str, Any]]) -> None:
    session = DummySession(polygon_sample_payloads)
    client = PolygonMarketDataClient(api_key="test", session=session)
    start = datetime(2024, 1, 2, 9, 30, tzinfo=timezone.utc)
    end = datetime(2024, 1, 2, 9, 31, tzinfo=timezone.utc)

    trades = client.get_trades("AAPL", start, end)
    quotes = client.get_nbbo("AAPL", start, end)

    assert not trades.empty
    assert not quotes.empty
    assert list(trades.columns) == [
        "timestamp",
        "price",
        "size",
        "exchange",
        "conditions",
        "sequence_number",
        "participant_timestamp",
        "trf_timestamp",
        "tape",
        "trade_id",
        "trf_id",
        "is_off_exchange",
    ]
    assert list(quotes.columns) == [
        "timestamp",
        "bid_price",
        "bid_size",
        "ask_price",
        "ask_size",
        "bid_exchange",
        "ask_exchange",
        "conditions",
        "sequence_number",
        "participant_timestamp",
        "trf_timestamp",
        "tape",
        "is_off_exchange",
    ]
    assert trades.loc[0, "timestamp"].tzinfo is not None
    assert quotes.loc[0, "timestamp"].tzinfo is not None
    assert isinstance(trades.loc[0, "conditions"], tuple)
    assert isinstance(quotes.loc[0, "conditions"], tuple)

    first_call = session.calls[0]
    assert first_call["params"]["timestamp.gte"].endswith("Z")
    assert first_call["params"]["apiKey"] == "test"


def test_create_client_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(DEFAULT_VENDOR_ENV_VAR, "polygon")
    monkeypatch.setenv("POLYGON_API_KEY", "key")
    client = create_market_data_client()
    assert isinstance(client, PolygonMarketDataClient)


def test_window_validation_requires_aware(monkeypatch: pytest.MonkeyPatch) -> None:
    session = DummySession([
        {"results": [], "next_url": None},
    ])
    client = PolygonMarketDataClient(api_key="test", session=session)
    start = datetime(2024, 1, 2, 9, 30)
    end = datetime(2024, 1, 2, 9, 31, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        client.get_trades("AAPL", start, end)
