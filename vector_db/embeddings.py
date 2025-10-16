"""Utility helpers for interacting with the pgvector-backed store."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Iterable, List, Sequence


@dataclass
class EmbeddingRecord:
    """Represents a vectorised artefact stored in Supabase."""

    identifier: str
    embedding: Sequence[float]
    metadata: dict[str, str]


def normalise_embeddings(vectors: Iterable[Sequence[float]]) -> List[List[float]]:
    """Return unit-normalised embeddings for cosine similarity search."""

    normalised: List[List[float]] = []
    for vector in vectors:
        arr = [float(value) for value in vector]
        norm = sqrt(sum(value * value for value in arr))
        normalised.append([value / norm if norm else value for value in arr])
    return normalised
