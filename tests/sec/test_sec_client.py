from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from framework import sec_client


SAMPLE_INDEX = b"""Description:
Form Type|Company Name|CIK|Date Filed|Filename
4|ACME INC|0000123456|2024-12-31|edgar/data/0000123456/0000123456-24-000001.txt
4/A|BETA LLC|0000002222|2024-12-31|edgar/data/0000002222/0000002222-24-000002.txt
"""


SAMPLE_XML = b"""<?xml version='1.0'?>
<ownershipDocument>
  <issuer>
    <issuerCik>0000123456</issuerCik>
    <issuerTradingSymbol>ACME</issuerTradingSymbol>
  </issuer>
  <reportingOwner>
    <reportingOwnerId>
      <rptOwnerName>John Doe</rptOwnerName>
    </reportingOwnerId>
  </reportingOwner>
  <accessionNumber>0000123456-24-000001</accessionNumber>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <transactionCoding>
        <transactionCode>P</transactionCode>
      </transactionCoding>
      <transactionDate>
        <value>2024-12-30</value>
      </transactionDate>
      <transactionAmounts>
        <transactionShares>
          <value>1,000</value>
        </transactionShares>
        <transactionPricePerShare>
          <value>10.5</value>
        </transactionPricePerShare>
      </transactionAmounts>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
  <derivativeTable>
    <derivativeTransaction>
      <transactionCoding>
        <transactionCode>A</transactionCode>
      </transactionCoding>
      <transactionDate>
        <value>2024-12-29</value>
      </transactionDate>
      <transactionAmounts>
        <transactionShares>
          <value>500</value>
        </transactionShares>
        <transactionPricePerShare>
          <value>0</value>
        </transactionPricePerShare>
      </transactionAmounts>
    </derivativeTransaction>
  </derivativeTable>
</ownershipDocument>
"""


def test_daily_index_urls_includes_plain_and_gzip():
    urls = sec_client.daily_index_urls(date(2024, 12, 31))
    assert urls[0].endswith("form.20241231.idx")
    assert urls[1].endswith("form.20241231.idx.gz")


def test_iter_form4_index_parses_rows(monkeypatch):
    fetched_urls: list[str] = []

    def fake_fetch(url: str) -> bytes:
        fetched_urls.append(url)
        return SAMPLE_INDEX

    monkeypatch.setattr(sec_client, "fetch_edgar_url", fake_fetch)
    rows = list(sec_client.iter_form4_index(date(2024, 12, 31)))
    assert fetched_urls[0].endswith("form.20241231.idx")
    assert len(rows) == 2
    first = rows[0]
    assert first.accession_number == "0000123456-24-000001"
    assert first.company_name == "ACME INC"
    assert first.cik == "0000123456"


def test_accession_to_primary_xml_url_handles_txt_path():
    url = sec_client.accession_to_primary_xml_url(
        "edgar/data/0000123456/0000123456-24-000001.txt"
    )
    assert url.endswith("/edgar/data/0000123456/0000123456-24-000001/primary_doc.xml")


def test_parse_form4_xml_extracts_transactions():
    parsed = sec_client.parse_form4_xml(SAMPLE_XML)
    assert parsed.symbol == "ACME"
    assert parsed.reporter == "John Doe"
    assert parsed.cik == "0000123456"
    assert parsed.accession == "0000123456-24-000001"
    assert len(parsed.transactions) == 2
    first = parsed.transactions[0]
    assert first.date.isoformat() == "2024-12-30"
    assert first.code == "P"
    assert first.shares == pytest.approx(1000.0)
    assert first.price == pytest.approx(10.5)
