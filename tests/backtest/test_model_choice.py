from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.model_selection import GridSearchCV
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MODULE_NAME = "flows.backtest"
MODULE_PATH = ROOT / "flows" / "backtest.py"

monitoring_pkg = types.ModuleType("monitoring")
drift_monitor_module = types.ModuleType("monitoring.drift_monitor")


class _DriftThresholdsStub:
    @classmethod
    def default(cls) -> "_DriftThresholdsStub":
        return cls()


def _evaluate_drift_stub(*args: object, **kwargs: object) -> types.SimpleNamespace:
    return types.SimpleNamespace(triggered=False)


def _handle_drift_stub(*args: object, **kwargs: object) -> None:
    return None


def _log_backtest_metrics_stub(*args: object, **kwargs: object) -> dict[str, object] | None:
    return None


def _summarize_evaluation_metrics_stub(*args: object, **kwargs: object) -> dict[str, float]:
    return {}


drift_monitor_module.DriftThresholds = _DriftThresholdsStub
drift_monitor_module.evaluate_drift = _evaluate_drift_stub
drift_monitor_module.handle_drift = _handle_drift_stub
drift_monitor_module.log_backtest_metrics = _log_backtest_metrics_stub
drift_monitor_module.summarize_evaluation_metrics = _summarize_evaluation_metrics_stub

monitoring_pkg.drift_monitor = drift_monitor_module

sys.modules.setdefault("monitoring", monitoring_pkg)
sys.modules.setdefault("monitoring.drift_monitor", drift_monitor_module)

spec = importlib.util.spec_from_file_location(MODULE_NAME, MODULE_PATH)
if spec is None or spec.loader is None:  # pragma: no cover - defensive
    raise RuntimeError("Unable to load flows.backtest module for testing")
backtest = importlib.util.module_from_spec(spec)
sys.modules[MODULE_NAME] = backtest
loader = spec.loader
assert loader is not None  # for type checking
loader.exec_module(backtest)
package = types.ModuleType("flows")
package.backtest = backtest
sys.modules.setdefault("flows", package)


def test_choose_model_catboost_falls_back_to_logistic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(backtest, "CatBoostClassifier", None)
    spec = backtest.choose_model("catboost", random_state=0)
    estimator = spec.builder()
    assert isinstance(estimator, Pipeline)
    assert spec.implementation == "sklearn.linear_model.LogisticRegression"
    assert spec.notes and "catboost" in spec.notes.lower()


def test_choose_model_tabpfn_falls_back_to_logistic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(backtest, "TabPFNClassifier", None)
    spec = backtest.choose_model("tabpfn", random_state=0)
    estimator = spec.builder()
    assert isinstance(estimator, Pipeline)
    assert spec.implementation == "sklearn.linear_model.LogisticRegression"
    assert spec.notes and "tabpfn" in spec.notes.lower()


def test_choose_model_tune_wraps_in_grid_search(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(backtest, "LGBMClassifier", None)
    spec = backtest.choose_model("lightgbm", random_state=0, mode="tune")
    estimator = spec.builder()
    assert isinstance(estimator, GridSearchCV)
    assert isinstance(estimator.estimator, Pipeline)


def test_choose_model_tabpfn_returns_classifier_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyTabPFNClassifier:
        def __init__(
            self,
            N_ensemble_configurations: int = 32,
            device: str = "cpu",
            random_state: int | None = None,
        ) -> None:
            self.N_ensemble_configurations = N_ensemble_configurations
            self.device = device
            self.random_state = random_state

        def get_params(self, deep: bool = True) -> dict[str, object]:
            return {
                "N_ensemble_configurations": self.N_ensemble_configurations,
                "device": self.device,
                "random_state": self.random_state,
            }

        def set_params(self, **params: object) -> "DummyTabPFNClassifier":
            for key, value in params.items():
                setattr(self, key, value)
            return self

    monkeypatch.setattr(backtest, "TabPFNClassifier", DummyTabPFNClassifier)
    spec = backtest.choose_model("tabpfn", random_state=7)
    estimator = spec.builder()
    assert isinstance(estimator, DummyTabPFNClassifier)
    assert estimator.random_state == 7
    assert spec.implementation == "tabpfn.TabPFNClassifier"
    assert spec.notes is None


def test_choose_model_tabpfn_tune_wraps_grid_search(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyTabPFNClassifier:
        def __init__(
            self,
            N_ensemble_configurations: int = 32,
            device: str = "cpu",
            random_state: int | None = None,
        ) -> None:
            self.N_ensemble_configurations = N_ensemble_configurations
            self.device = device
            self.random_state = random_state

        def get_params(self, deep: bool = True) -> dict[str, object]:
            return {
                "N_ensemble_configurations": self.N_ensemble_configurations,
                "device": self.device,
                "random_state": self.random_state,
            }

        def set_params(self, **params: object) -> "DummyTabPFNClassifier":
            for key, value in params.items():
                setattr(self, key, value)
            return self

    monkeypatch.setattr(backtest, "TabPFNClassifier", DummyTabPFNClassifier)
    spec = backtest.choose_model("tabpfn", random_state=7, mode="tune")
    estimator = spec.builder()
    assert isinstance(estimator, GridSearchCV)
    assert isinstance(estimator.estimator, DummyTabPFNClassifier)
    assert estimator.param_grid["N_ensemble_configurations"] == [16, 32]


def test_arg_parser_includes_tabpfn_choice() -> None:
    parser = backtest._build_arg_parser()
    model_action = next(action for action in parser._actions if action.dest == "model")
    assert model_action.choices is not None
    assert "tabpfn" in model_action.choices


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
