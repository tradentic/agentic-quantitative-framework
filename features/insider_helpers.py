from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Mapping

from framework.sec_parse import ReportingOwner


def _extract_officer_title(block: Any) -> str | None:
    if isinstance(block, ReportingOwner):
        return block.officer_title
    if isinstance(block, Mapping):
        value = block.get("officer_title") or block.get("officerTitle")
        if value:
            return str(value)
    if hasattr(block, "officer_title"):
        value = getattr(block, "officer_title")
        if value is not None:
            return str(value)
    return None


def is_ceo(reporting_owner_block: Any) -> bool:
    """Return True when the reporting owner's officer title contains 'CEO'."""

    title = _extract_officer_title(reporting_owner_block)
    if not title:
        return False
    return "CEO" in title.upper()


def is_recent_filing(filing_date: date | datetime | None, now: datetime | None = None, *, days: int = 7) -> bool:
    """Return True when the filing date is within the provided lookback window."""

    if filing_date is None:
        return False
    if isinstance(filing_date, datetime):
        filing_date = filing_date.date()
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    today = now.date()
    delta = today - filing_date
    return delta.days >= 0 and delta.days <= max(days, 0)


__all__ = ["is_ceo", "is_recent_filing"]
