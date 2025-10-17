"""Stub definitions for the future HMM-based change point feature module."""

from __future__ import annotations

from typing import Mapping


def planned_feature_schema() -> Mapping[str, str]:
    """Describe the columns the eventual HMM change-point feature generator will emit."""

    return {
        "hmm_state": "Most likely hidden state label inferred at the end of the window.",
        "state_probability": "Probability assigned to the most likely hidden state.",
        "change_point_score": "Smoothed statistic indicating proximity to a regime change.",
    }


def describe_feature_strategy() -> str:
    """Return narrative guidance on how the change-point features will be derived."""

    return (
        "This module will fit a Hidden Markov Model over rolling returns and volume "
        "signatures, emitting state probabilities and the distance to the most "
        "recent detected change point for downstream models."
    )


__all__ = ["planned_feature_schema", "describe_feature_strategy"]
