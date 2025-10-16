from __future__ import annotations

import io
import zipfile
from datetime import date
from pathlib import Path
import sys

import pytest

sys.path.append(str(Path(__file__).resolve().parents[2]))

from framework import finra_client


@pytest.fixture(autouse=True)
def clear_caches():
    finra_client._short_volume_by_symbol.cache_clear()
    finra_client._ats_week_by_symbol.cache_clear()
    yield
    finra_client._short_volume_by_symbol.cache_clear()
    finra_client._ats_week_by_symbol.cache_clear()


def test_get_short_volume_parses_pipe_delimited(monkeypatch):
    sample = (
        "Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market\n"
        "2024-04-01|AAPL|100|5|1000|N\n"
        "2024-04-01|MSFT|250|10|2000|N\n"
    )

    monkeypatch.setattr(finra_client, "_try_urls", lambda urls: sample.encode("utf-8"))

    record = finra_client.get_short_volume("AAPL", date(2024, 4, 1))
    assert record is not None
    assert record.short_volume == 100
    assert pytest.approx(record.short_share, rel=1e-9) == 0.1
    assert pytest.approx(record.short_exempt_share, rel=1e-9) == 0.005


def test_get_ats_week_aggregates_zip_payload(monkeypatch):
    text = (
        "MarketParticipantIdentifier|Week|Symbol|Shares|Trades|TotalWeeklyShareVolume|TotalWeeklyTradeCount\n"
        "MP1|2024-04-12|AAPL|100|5|1000|50\n"
        "MP2|2024-04-12|AAPL|150|7|1000|50\n"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("ATS_W_Summary_20240412.txt", text)
    buffer.seek(0)

    monkeypatch.setattr(finra_client, "_try_urls", lambda urls: buffer.getvalue())

    week = date(2024, 4, 12)
    record = finra_client.get_ats_week("AAPL", week)
    assert record is not None
    assert record.ats_share_volume == 250
    assert record.ats_trade_count == 12
    assert record.total_weekly_trade_count == 50
    assert pytest.approx(record.ats_share_of_total or 0.0, rel=1e-9) == 0.25
