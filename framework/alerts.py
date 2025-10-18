from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

import requests

from framework.supabase_client import MissingSupabaseConfiguration, get_supabase_client

LOGGER = logging.getLogger(__name__)


@dataclass
class Alert:
    symbol: str
    severity: str
    payload: dict[str, Any]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data


def dispatch_alert(alert: Alert) -> None:
    """Emit the alert to the configured sink(s)."""

    record = alert.to_dict()
    webhook_url = (os.getenv("ALERT_WEBHOOK_URL") or "").strip()
    sink_used = False

    try:
        client = get_supabase_client()
    except MissingSupabaseConfiguration:
        client = None
    if client is not None:
        try:
            client.table("insider_alerts").insert(record).execute()
            sink_used = True
        except Exception as exc:  # pragma: no cover - defensive log
            LOGGER.warning("Failed to persist alert to Supabase: %s", exc)

    if webhook_url:
        try:
            response = requests.post(webhook_url, json=record, timeout=5)
            response.raise_for_status()
            sink_used = True
        except Exception as exc:  # pragma: no cover - defensive log
            LOGGER.warning("Failed to POST alert webhook: %s", exc)

    if not sink_used:
        LOGGER.info("[ALERT] %s", json.dumps(record, sort_keys=True))


__all__ = ["Alert", "dispatch_alert"]
