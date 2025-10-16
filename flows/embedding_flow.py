"""Prefect flow that refreshes embeddings when new windows arrive."""

from __future__ import annotations

from typing import Any

from agents.tools import poll_embedding_jobs, refresh_vector_store
from framework.supabase_client import mark_embedding_job_complete
from prefect import flow, get_run_logger, task


@task
def fetch_pending_jobs(limit: int) -> list[dict[str, Any]]:
    logger = get_run_logger()
    jobs = poll_embedding_jobs(limit=limit)
    logger.info("Fetched %d pending embedding jobs", len(jobs))
    return jobs


@task
def process_embedding_job(job: dict[str, Any]) -> dict[str, Any]:
    logger = get_run_logger()
    refresh_vector_store(
        {
            "asset_symbol": job.get("asset_symbol"),
            "windows": job.get("windows", []),
            "metadata": job.get("metadata", {}),
        }
    )
    if job.get("id"):
        mark_embedding_job_complete(job["id"])
    logger.info("Processed embedding job %s", job.get("id"))
    return job


@flow(name="supabase-embedding-refresh")
def supabase_embedding_refresh(limit: int = 5) -> list[dict[str, Any]]:
    """Main orchestration entry point triggered by Supabase realtime events."""

    jobs = fetch_pending_jobs(limit)
    results: list[dict[str, Any]] = []
    for job in jobs:
        results.append(process_embedding_job(job))
    return results


__all__ = ["supabase_embedding_refresh"]
