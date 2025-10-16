"""Tests for DeepLOB embedding utilities."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("torch")

import torch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from features.deeplob_embeddings import DeepLOBConfig, deeplob_embeddings, load_deeplob_model


def test_deeplob_embeddings_returns_expected_shape() -> None:
    config = DeepLOBConfig(in_channels=2, conv_channels=(8, 16), inception_channels=16, lstm_hidden_size=32)
    model = load_deeplob_model(config=config, device="cpu")
    book = torch.randn(10, config.in_channels, 32, 16)

    vectors = deeplob_embeddings(book, model=model, batch_size=4)

    assert vectors.shape == (10, config.lstm_hidden_size)
    assert vectors.dtype == torch.float32


def test_deeplob_embeddings_auto_model_cpu_fallback() -> None:
    book = torch.randn(5, 1, 40, 32)

    vectors = deeplob_embeddings(book, batch_size=2)

    assert vectors.shape[0] == book.shape[0]
    assert vectors.shape[1] == DeepLOBConfig().lstm_hidden_size
    assert torch.all(torch.isfinite(vectors))
