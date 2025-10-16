"""Utility helpers for connecting to Supabase within the agent runtime."""

from __future__ import annotations

import os
from functools import lru_cache
from importlib import import_module, util
from typing import Any, Dict

ENV_URL_KEYS = ("SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL")
ENV_KEY_KEYS = (
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_ANON_KEY",
    "NEXT_PUBLIC_SUPABASE_ANON_KEY",
)


class MissingSupabaseConfiguration(RuntimeError):
    """Raised when the required Supabase environment variables are missing."""


def _load_supabase_client_factory() -> Any:
    """Dynamically import and return the Supabase client's factory function."""

    if util.find_spec("supabase") is None:
        raise ModuleNotFoundError(
            "The `supabase` Python client is required. Install it with `pip install supabase`.",
        )
    module = import_module("supabase")
    create_client = getattr(module, "create_client", None)
    if create_client is None:
        raise AttributeError("The Supabase client module does not expose `create_client`.")
    return create_client


def _resolve_env_value(candidates: tuple[str, ...]) -> str | None:
    for key in candidates:
        value = os.getenv(key)
        if value:
            return value
    return None


@lru_cache(maxsize=1)
def get_supabase_client() -> Any:
    """Return a cached Supabase client instance configured from the environment."""

    url = _resolve_env_value(ENV_URL_KEYS)
    key = _resolve_env_value(ENV_KEY_KEYS)
    if not url or not key:
        raise MissingSupabaseConfiguration(
            "Supabase credentials are not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in the environment.",
        )
    factory = _load_supabase_client_factory()
    return factory(url, key)


def build_metadata(metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Coerce optional metadata dictionaries into a Supabase-friendly payload."""

    return metadata.copy() if metadata else {}
