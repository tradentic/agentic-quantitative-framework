"""Provenance utilities to track data lineage within the framework."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime, timezone
from typing import Any, Mapping, MutableMapping, Sequence

from framework.supabase_client import MissingSupabaseConfiguration, get_supabase_client

PROVENANCE_TABLE = os.getenv("SUPABASE_PROVENANCE_TABLE", "provenance_events")
FORM4_PARSER_VERSION = os.getenv("FORM4_PARSER_VERSION", "form4-xml-v1")
OFFEX_FEATURE_VERSION = os.getenv("OFFEX_FEATURE_VERSION", "offexchange-features-v1")


def hash_bytes(payload: bytes, *, algorithm: str = "sha256") -> str:
    """Return a hexadecimal digest for the provided byte payload."""

    if not isinstance(payload, (bytes, bytearray)):
        message = "hash_bytes expects a bytes-like object"
        raise TypeError(message)
    digest = hashlib.new(algorithm)
    digest.update(payload)
    return digest.hexdigest()


def _stringify(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore")
    if isinstance(value, Mapping):
        return {str(key): _stringify(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_stringify(item) for item in value]
    return str(value)


def _normalize_pk(pk: Any) -> str:
    if isinstance(pk, (str, int)):
        return str(pk)
    if isinstance(pk, Mapping):
        sanitized = {str(key): _stringify(value) for key, value in pk.items()}
        return json.dumps(sanitized, sort_keys=True)
    return json.dumps(_stringify(pk), sort_keys=True)


def _sanitize_meta(meta: Mapping[str, Any] | None) -> MutableMapping[str, Any]:
    payload: MutableMapping[str, Any] = {}
    if not meta:
        return payload
    for key, value in meta.items():
        payload[str(key)] = _stringify(value)
    return payload


def record_provenance(table: str, pk: Any, meta: Mapping[str, Any] | None = None) -> None:
    """Persist a provenance row associated with a Supabase table record."""

    metadata = _sanitize_meta(meta)
    metadata.setdefault("fetched_at", datetime.now(timezone.utc).isoformat())
    payload = {
        "table_name": table,
        "record_id": _normalize_pk(pk),
        "meta": metadata,
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        client = get_supabase_client()
    except MissingSupabaseConfiguration:
        return
    client.table(PROVENANCE_TABLE).upsert(payload, on_conflict="table_name,record_id").execute()


__all__ = [
    "FORM4_PARSER_VERSION",
    "OFFEX_FEATURE_VERSION",
    "PROVENANCE_TABLE",
    "hash_bytes",
    "record_provenance",
]
