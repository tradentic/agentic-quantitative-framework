from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from alerts.insider_nvda import evaluate_nvda_insider_alert
from features.price_trend import PriceTrend
from framework.sec_client import parse_form4_xml


def _load_fixture(name: str) -> bytes:
    fixture_path = Path(__file__).parent.parent / "fixtures" / name
    return fixture_path.read_bytes()


def test_alert_emitted_when_ceo_and_trend_up():
    xml_bytes = _load_fixture("form4_ceo.xml")
    parsed = parse_form4_xml(xml_bytes)
    filings = [
        {
            "parsed": parsed,
            "xml_bytes": xml_bytes,
            "filing_date": parsed.filing_date.isoformat() if parsed.filing_date else "2024-07-02",
        }
    ]
    fake_trend = PriceTrend(ret_5d=0.05, high_20d=True, trend_up=True)
    with patch("alerts.insider_nvda.evaluate_price_trend", return_value=fake_trend):
        alert = evaluate_nvda_insider_alert(
            symbol="NVDA",
            filings=filings,
            emit=False,
            now=datetime(2024, 7, 5, tzinfo=timezone.utc),
        )
    assert alert is not None
    assert alert.severity == "HIGH"
    assert alert.payload["ceo_filings"] == 1
    assert alert.payload["trend_up"] is True


def test_alert_suppressed_without_trend_confirmation():
    xml_bytes = _load_fixture("form4_ceo.xml")
    parsed = parse_form4_xml(xml_bytes)
    filings = [
        {
            "parsed": parsed,
            "xml_bytes": xml_bytes,
            "filing_date": parsed.filing_date.isoformat() if parsed.filing_date else "2024-07-02",
        }
    ]
    fake_trend = PriceTrend(ret_5d=-0.02, high_20d=False, trend_up=False)
    with patch("alerts.insider_nvda.evaluate_price_trend", return_value=fake_trend):
        alert = evaluate_nvda_insider_alert(
            symbol="NVDA",
            filings=filings,
            emit=False,
            now=datetime(2024, 7, 5, tzinfo=timezone.utc),
        )
    assert alert is None


def test_alert_requires_ceo_reporting_owner():
    xml_bytes = _load_fixture("form4_ceo.xml")
    parsed = parse_form4_xml(xml_bytes)
    parsed_no_ceo = replace(parsed, reporting_owners=tuple())
    filings = [
        {
            "parsed": parsed_no_ceo,
            "xml_bytes": xml_bytes,
            "filing_date": "2024-07-02",
        }
    ]
    fake_trend = PriceTrend(ret_5d=0.05, high_20d=True, trend_up=True)
    with patch("alerts.insider_nvda.evaluate_price_trend", return_value=fake_trend):
        alert = evaluate_nvda_insider_alert(
            symbol="NVDA",
            filings=filings,
            emit=False,
            now=datetime(2024, 7, 5, tzinfo=timezone.utc),
        )
    assert alert is None
