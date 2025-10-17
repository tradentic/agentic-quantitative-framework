"""Stub documentation for topological persistence feature planning."""

from __future__ import annotations

from typing import Mapping


def planned_persistence_features() -> Mapping[str, str]:
    """Describe the persistence-summary features that will be materialised."""

    return {
        "lifespan_max": "Maximum bar lifespan observed in the persistence diagram.",
        "lifespan_mean": "Average persistence across significant homology classes.",
        "birth_time_entropy": "Entropy of birth times for 0/1-dimensional features.",
    }


def persistence_feature_notes() -> str:
    """Provide implementation notes for future developers."""

    return (
        "Persistence-based features will operate on rolling price-depth complexes, "
        "tracking how quickly connected components and loops die out. The actual "
        "implementation should stream persistence diagrams and normalise summaries "
        "per symbol to avoid look-ahead bias."
    )


__all__ = ["planned_persistence_features", "persistence_feature_notes"]
