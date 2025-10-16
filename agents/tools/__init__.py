"""Operational tools invoked by LangGraph nodes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Dict, Iterable, List


def propose_new_feature(
    feature_log: Iterable[Dict[str, float | str]], objective: str
) -> Dict[str, str]:
    """Suggest the next feature engineering experiment.

    The heuristic scans the provided ``feature_log`` (ordered dictionaries
    that contain ``sharpe`` and ``coverage`` scores) and proposes either
    an extension of the best performing feature or a diversification step
    when performance has plateaued.
    """

    feature_log = list(feature_log)
    if not feature_log:
        return {
            "name": "ts2vec_signal",
            "transform": "ts2vec_embedding",
            "rationale": (
                "Bootstrap the signal library with a TS2Vec representation "
                "to seed the vector memory."
            ),
        }

    top_feature = max(feature_log, key=lambda record: record.get("sharpe", 0.0))
    if top_feature.get("sharpe", 0.0) < 0.75:
        return {
            "name": "volatility_regime_mix",
            "transform": "rolling_zscore(returns, window=48) * regime_label",
            "rationale": (
                "Sharpe has not crossed 0.75, so widen search with a "
                "regime-aware volatility oscillator."
            ),
        }

    return {
        "name": f"{top_feature.get('name', 'feature')}_interaction",
        "transform": f"{top_feature.get('name', 'feature')} * liquidity_premium",
        "rationale": (
            "Reinforce the leading feature by pairing it with a liquidity "
            "premium proxy to test persistence while pursuing the "
            f"objective '{objective}'."
        ),
    }


def run_backtest(feature_plan: Dict[str, str]) -> Dict[str, float]:
    """Return synthetic backtest metrics for the planned feature.

    The planner records deterministic metrics so that automation and
    documentation flows remain reproducible.
    """

    feature_name = feature_plan.get("name", "unknown")
    base_score = 0.6 if "volatility" in feature_name else 0.85
    sharpe = base_score + 0.05
    calmar = base_score - 0.1
    max_dd = -0.12 if base_score > 0.7 else -0.2
    return {
        "sharpe": round(sharpe, 3),
        "calmar": round(calmar, 3),
        "max_drawdown": round(max_dd, 3),
    }


def prune_vectors(last_refresh: datetime, drift_score: float) -> str:
    """Describe pruning action triggered by drift monitoring."""

    age_days = max((datetime.now(tz=UTC) - last_refresh).days, 0)

    if drift_score < 0.3:
        return (
            "No pruning required; embeddings are within tolerance and the "
            f"index is {age_days} days old."
        )
    if drift_score < 0.6:
        return (
            "Prune tail embeddings older than 90 days and refresh "
            f"volatility clusters (index age {age_days} days)."
        )
    return (
        "Aggressively prune stale clusters and schedule full re-index; "
        f"current index age is {age_days} days."
    )


def refresh_vector_store(reason: str, target_collections: List[str]) -> str:
    """Request a vector store refresh for the supplied collections."""

    formatted_targets = ", ".join(target_collections) or "all collections"
    return f"Refresh {formatted_targets} because {reason.strip().rstrip('.')}."


__all__ = [
    "propose_new_feature",
    "run_backtest",
    "prune_vectors",
    "refresh_vector_store",
]
