from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from features.insider_helpers import is_ceo, is_recent_filing
from framework.sec_client import parse_form4_xml


def _load_fixture(name: str) -> bytes:
    fixture_path = Path(__file__).parent.parent / "fixtures" / name
    return fixture_path.read_bytes()


def test_parse_form4_exposes_reporting_owner_title():
    xml_bytes = _load_fixture("form4_ceo.xml")
    parsed = parse_form4_xml(xml_bytes)
    assert parsed.reporting_owners, "expected reporting owners to be parsed"
    owner = parsed.reporting_owners[0]
    assert owner.officer_title == "President and CEO"
    assert is_ceo(owner)


def test_is_recent_filing_within_window():
    xml_bytes = _load_fixture("form4_ceo.xml")
    parsed = parse_form4_xml(xml_bytes)
    now = datetime(2024, 7, 5, tzinfo=timezone.utc)
    assert parsed.filing_date is not None
    assert is_recent_filing(parsed.filing_date, now=now, days=7)


def test_is_ceo_false_when_title_missing():
    xml_bytes = _load_fixture("form4_ceo.xml")
    parsed = parse_form4_xml(xml_bytes)
    without_title = replace(parsed.reporting_owners[0], officer_title=None)
    assert not is_ceo(without_title)
