from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.model_selection import GridSearchCV
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import flows.backtest as backtest


def test_choose_model_catboost_falls_back_to_logistic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(backtest, "CatBoostClassifier", None)
    spec = backtest.choose_model("catboost", random_state=0)
    estimator = spec.builder()
    assert isinstance(estimator, Pipeline)
    assert spec.implementation == "sklearn.linear_model.LogisticRegression"
    assert spec.notes and "catboost" in spec.notes.lower()


def test_choose_model_tune_wraps_in_grid_search(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(backtest, "LGBMClassifier", None)
    spec = backtest.choose_model("lightgbm", random_state=0, mode="tune")
    estimator = spec.builder()
    assert isinstance(estimator, GridSearchCV)
    assert isinstance(estimator.estimator, Pipeline)


def test_train_and_evaluate_uses_choose_model(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, tuple[str, int, str]] = {}

    class DummyEstimator:
        def __init__(self) -> None:
            self.mean_: float = 0.5

        def fit(self, X: pd.DataFrame, y: pd.Series) -> DummyEstimator:  # noqa: N803 - sklearn style
            self.mean_ = float(np.mean(y))
            return self

        def predict_proba(self, X: pd.DataFrame) -> np.ndarray:  # noqa: N803 - sklearn style
            proba = np.full(len(X), self.mean_)
            return np.column_stack([1 - proba, proba])

    def fake_choose(model_type: str, *, random_state: int, mode: str) -> backtest.ModelSpec:
        calls["args"] = (model_type, random_state, mode)
        return backtest.ModelSpec(
            name="dummy",
            implementation="tests.dummy",
            builder=lambda: DummyEstimator(),
        )

    monkeypatch.setattr(backtest, "choose_model", fake_choose)

    train_df = pd.DataFrame({"feature": [0.0, 1.0, 2.0, 3.0], "label": [0, 1, 0, 1]})
    validation_df = pd.DataFrame({"feature": [4.0, 5.0, 6.0, 7.0], "label": [0, 0, 1, 1]})

    results = backtest.train_and_evaluate(
        train_df,
        validation_df,
        feature_columns=["feature"],
        target_column="label",
        random_state=0,
        calibration_bins=2,
        model_type="catboost",
        mode="train",
    )

    assert calls["args"] == ("catboost", 0, "train")
    assert len(results) == 1
    assert results[0].model_name == "dummy"
    assert "roc_auc" in results[0].metrics
