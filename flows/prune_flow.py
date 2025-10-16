"""Prefect flow that prunes stale embeddings on a schedule."""

from __future__ import annotations

from typing import Any

from agents.tools import prune_vectors
from prefect import flow, get_run_logger, task


@task
def trigger_prune(criteria: dict[str, Any]) -> dict[str, Any]:
    logger = get_run_logger()
    result = prune_vectors(criteria)
    logger.info("Prune result: %s", result.get("result"))
    return result


@flow(name="scheduled-vector-prune")
def scheduled_vector_prune(**criteria: Any) -> dict[str, Any]:
    """Entry point invoked by Prefect schedules or manual triggers."""

    default_criteria = {"max_age_days": 90, "min_t_stat": 0.5, "regime_diversity": 3}
    default_criteria.update(criteria)
    return trigger_prune(default_criteria)


__all__ = ["scheduled_vector_prune"]
