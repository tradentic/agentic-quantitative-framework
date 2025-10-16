"""Feature generation modules for embeddings and signals."""

from . import generate_ts2vec_embeddings
from .matrix_profile import MatrixProfileFeatures, compute_matrix_profile_metrics

__all__ = [
    "generate_ts2vec_embeddings",
    "compute_matrix_profile_metrics",
    "MatrixProfileFeatures",
]
