"""Prefect flow that schedules Supabase-backed backtests."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from agents.tools import run_backtest
from framework.supabase_client import MissingSupabaseConfiguration, get_supabase_client
from prefect import flow, get_run_logger, task


@task
def fetch_pending_backtests(limit: int = 5) -> list[dict[str, Any]]:
    logger = get_run_logger()
    try:
        client = get_supabase_client()
    except MissingSupabaseConfiguration:
        logger.warning("Supabase credentials missing; returning empty backtest queue.")
        return []
    response = (
        client.table("backtest_requests")
        .select("*")
        .eq("status", "pending")
        .order("created_at")
        .limit(limit)
        .execute()
    )
    requests = getattr(response, "data", []) or []
    logger.info("Fetched %d backtest requests", len(requests))
    return requests


@task
def execute_backtest_request(request: dict[str, Any]) -> dict[str, Any]:
    logger = get_run_logger()
    config = request.get("config") or {}
    config.setdefault("strategy_id", request.get("strategy_id", "unknown"))
    run_backtest(config)
    try:
        client = get_supabase_client()
        client.table("backtest_requests").update(
            {
                "status": "completed",
                "completed_at": datetime.utcnow().isoformat(),
            }
        ).eq("id", request.get("id")).execute()
    except MissingSupabaseConfiguration:
        logger.debug("Supabase unavailable; skipping request status update.")
    logger.info("Completed backtest request %s", request.get("id"))
    return request


@flow(name="scheduled-backtest-runner")
def scheduled_backtest_runner(limit: int = 5) -> list[dict[str, Any]]:
    """Run pending backtests in batches."""

    queue = fetch_pending_backtests(limit)
    results: list[dict[str, Any]] = []
    for request in queue:
        results.append(execute_backtest_request(request))
    return results


__all__ = ["scheduled_backtest_runner"]
