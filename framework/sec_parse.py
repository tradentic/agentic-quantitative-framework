from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable, Iterator
import xml.etree.ElementTree as ET


@dataclass(frozen=True)
class ReportingOwner:
    """Normalized block describing a reporting owner within a Form 4."""

    name: str
    cik: str | None
    officer_title: str | None
    is_director: bool | None
    is_officer: bool | None
    is_ten_percent_owner: bool | None
    is_other: bool | None
    other_text: str | None


def find_text(node: ET.Element | Iterable, tag: str) -> str | None:
    """Return the first non-empty string for a tag within the provided node."""

    iter_nodes: Iterator = getattr(node, "iter", lambda: [])()
    for child in iter_nodes:
        if isinstance(getattr(child, "tag", None), str) and child.tag.split("}")[-1] == tag:
            text = (child.text or "").strip()
            if text:
                return text
            for sub in getattr(child, "iter", lambda: [])():
                sub_text = (getattr(sub, "text", "") or "").strip()
                if sub_text:
                    return sub_text
    return None


def parse_issuer_name(root: ET.Element) -> str | None:
    return find_text(root, "issuerName")


def parse_filing_date(root: ET.Element) -> date | None:
    for tag in ("documentPeriodEndingDate", "periodOfReport", "signatureDate", "dateOfReport"):
        text = find_text(root, tag)
        if text:
            try:
                return datetime.strptime(text.strip(), "%Y-%m-%d").date()
            except ValueError:
                continue
    return None


def _coerce_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes"}:
        return True
    if normalized in {"0", "false", "no"}:
        return False
    return None


def parse_reporting_owners(root: ET.Element) -> tuple[ReportingOwner, ...]:
    owners: list[ReportingOwner] = []
    for owner_node in root.findall(".//{*}reportingOwner"):
        name = find_text(owner_node, "rptOwnerName") or ""
        cik = find_text(owner_node, "rptOwnerCik")
        officer_title = find_text(owner_node, "officerTitle")
        is_director = _coerce_bool(find_text(owner_node, "isDirector"))
        is_officer = _coerce_bool(find_text(owner_node, "isOfficer"))
        is_ten_percent = _coerce_bool(find_text(owner_node, "isTenPercentOwner"))
        is_other = _coerce_bool(find_text(owner_node, "isOther"))
        other_text = find_text(owner_node, "otherText")
        owners.append(
            ReportingOwner(
                name=name,
                cik=cik,
                officer_title=officer_title,
                is_director=is_director,
                is_officer=is_officer,
                is_ten_percent_owner=is_ten_percent,
                is_other=is_other,
                other_text=other_text,
            )
        )
    return tuple(owners)


__all__ = ["ReportingOwner", "find_text", "parse_filing_date", "parse_issuer_name", "parse_reporting_owners"]
