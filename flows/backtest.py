"""Prefect flow implementing the insider pre-filing classifier backtest."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, Sequence

import json
import math

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from prefect import flow, get_run_logger
from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    log_loss,
    precision_recall_curve,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

try:
    from lightgbm import LGBMClassifier
except Exception:  # pragma: no cover - optional dependency
    LGBMClassifier = None  # type: ignore[assignment]

try:
    from xgboost import XGBClassifier
except Exception:  # pragma: no cover - optional dependency
    XGBClassifier = None  # type: ignore[assignment]

try:
    from catboost import CatBoostClassifier
except Exception:  # pragma: no cover - optional dependency
    CatBoostClassifier = None  # type: ignore[assignment]


@dataclass(slots=True)
class InsiderBacktestConfig:
    """Configuration for the insider pre-filing classifier backtest flow."""

    windows_path: Path
    filings_path: Path
    label_horizon_days: int = 5
    validation_fraction: float = 0.2
    report_dir: Path = Path("reports/backtests")
    random_state: int = 42
    calibration_bins: int = 10
    window_end_column: str = "window_end"
    window_symbol_column: str = "symbol"
    filing_date_column: str = "filing_date"
    filing_symbol_column: str = "symbol"
    model: str = "lightgbm"
    mode: str = "train"


@dataclass(slots=True)
class ModelSpec:
    """Container describing a baseline model implementation."""

    name: str
    builder: Callable[[], object]
    implementation: str
    notes: str | None = None


@dataclass(slots=True)
class EvaluationResult:
    """Evaluation artefacts for a trained model."""

    model_name: str
    implementation: str
    notes: str | None
    metrics: dict[str, float]
    y_true: np.ndarray
    y_score: np.ndarray


@dataclass(slots=True)
class BacktestArtifacts:
    """Paths to artefacts produced by the backtest flow."""

    metrics_path: Path
    roc_curve_path: Path
    pr_curve_path: Path
    calibration_path: Path


def _coerce_datetime(series: pd.Series) -> pd.Series:
    converted = pd.to_datetime(series, utc=True, errors="coerce")
    if converted.isna().any():
        raise ValueError("Datetime conversion produced NaT values; check input data.")
    return converted.dt.tz_convert(None)


def load_table(path: Path) -> pd.DataFrame:
    """Load a tabular dataset from CSV or Parquet into a dataframe."""

    resolved = Path(path).expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Dataset not found at {resolved}")
    if resolved.suffix.lower() in {".csv", ".txt"}:
        return pd.read_csv(resolved)
    if resolved.suffix.lower() in {".parquet", ".pq"}:
        return pd.read_parquet(resolved)
    raise ValueError(f"Unsupported file extension for {resolved}")


def build_labels(
    windows: pd.DataFrame,
    filings: pd.DataFrame,
    *,
    symbol_column: str,
    window_end_column: str,
    filing_symbol_column: str,
    filing_date_column: str,
    horizon_days: int,
) -> pd.DataFrame:
    """Assign weak labels to windows when a Form 4 occurs within the lookahead horizon."""

    if horizon_days <= 0:
        raise ValueError("horizon_days must be positive")

    windows = windows.copy()
    filings = filings.copy()

    windows[symbol_column] = windows[symbol_column].astype(str)
    filings[filing_symbol_column] = filings[filing_symbol_column].astype(str)

    windows[window_end_column] = _coerce_datetime(windows[window_end_column])
    filings[filing_date_column] = _coerce_datetime(filings[filing_date_column])

    horizon = pd.Timedelta(days=horizon_days)

    labels: list[int] = []
    distances: list[float] = []

    filings_grouped = filings.groupby(filing_symbol_column)

    for symbol, window_group in windows.groupby(symbol_column):
        filing_dates = filings_grouped.get_group(symbol)[filing_date_column].sort_values().to_numpy() if symbol in filings_grouped.groups else np.array([], dtype="datetime64[ns]")
        window_ends = window_group[window_end_column].sort_values()
        symbol_labels = []
        symbol_distances = []

        for window_end in window_ends:
            if filing_dates.size == 0:
                symbol_labels.append(0)
                symbol_distances.append(math.inf)
                continue
            idx = np.searchsorted(filing_dates, window_end.to_datetime64(), side="left")
            positive = 0
            min_distance = math.inf
            if idx < filing_dates.size:
                distance = (filing_dates[idx] - window_end.to_datetime64()) / np.timedelta64(1, "D")
                if 0 <= distance <= horizon.days:
                    positive = 1
                    min_distance = float(distance)
            if idx > 0 and positive == 0:
                distance = (filing_dates[idx - 1] - window_end.to_datetime64()) / np.timedelta64(1, "D")
                if 0 <= distance <= horizon.days:
                    positive = 1
                    min_distance = min(min_distance, float(distance))
            symbol_labels.append(positive)
            symbol_distances.append(min_distance)

        ordered = window_group.assign(
            label=symbol_labels,
            days_until_filing=symbol_distances,
        ).sort_values(window_end_column)
        labels.extend(ordered["label"].tolist())
        distances.extend(ordered["days_until_filing"].tolist())

    labeled = windows.sort_values([symbol_column, window_end_column]).copy()
    labeled["label"] = labels
    labeled["days_until_filing"] = distances
    return labeled


def time_based_split(
    frame: pd.DataFrame,
    *,
    time_column: str,
    validation_fraction: float,
) -> tuple[pd.Index, pd.Index]:
    """Split a dataframe into train and validation sets using chronological ordering."""

    if not 0 < validation_fraction < 1:
        raise ValueError("validation_fraction must be between 0 and 1")

    ordered = frame.sort_values(time_column)
    cutoff = int(len(ordered) * (1 - validation_fraction))
    cutoff = max(1, min(cutoff, len(ordered) - 1))
    cutoff_time = ordered.iloc[cutoff][time_column]
    train_index = ordered[ordered[time_column] <= cutoff_time].index
    validation_index = ordered[ordered[time_column] > cutoff_time].index
    return train_index, validation_index


def _select_feature_columns(df: pd.DataFrame, *, exclude: Iterable[str]) -> list[str]:
    excluded = set(exclude)
    features = [col for col in df.columns if col not in excluded and pd.api.types.is_numeric_dtype(df[col])]
    if not features:
        raise ValueError("No numeric feature columns found for training")
    return features


def _build_logistic_pipeline(random_state: int) -> Pipeline:
    return Pipeline(
        steps=[
            ("scale", StandardScaler()),
            (
                "clf",
                __import__("sklearn.linear_model", fromlist=["LogisticRegression"]).LogisticRegression(
                    solver="lbfgs",
                    max_iter=1000,
                    random_state=random_state,
                ),
            ),
        ]
    )


def choose_model(model_type: str, *, random_state: int, mode: str = "train") -> ModelSpec:
    """Return a ``ModelSpec`` for the requested model and execution mode."""

    normalized = model_type.lower()
    if mode not in {"train", "tune"}:
        raise ValueError("mode must be 'train' or 'tune'")

    notes: str | None = None
    implementation: str

    def build_logistic() -> Pipeline:
        return _build_logistic_pipeline(random_state)

    if normalized == "xgboost":
        if XGBClassifier is None:
            implementation = "sklearn.linear_model.LogisticRegression"
            notes = "xgboost package not installed; falling back to logistic regression"

            def base_builder() -> Pipeline:
                return build_logistic()

            param_grid = {"clf__C": [0.1, 1.0, 10.0]}
        else:
            implementation = "xgboost.XGBClassifier"

            def base_builder() -> object:
                return XGBClassifier(
                    n_estimators=200,
                    max_depth=4,
                    learning_rate=0.05,
                    subsample=0.8,
                    colsample_bytree=0.8,
                    eval_metric="logloss",
                    random_state=random_state,
                    tree_method="hist",
                    use_label_encoder=False,
                )

            param_grid = {"n_estimators": [150, 250], "max_depth": [3, 4]}
    elif normalized == "lightgbm":
        if LGBMClassifier is None:
            implementation = "sklearn.linear_model.LogisticRegression"
            notes = "lightgbm package not installed; falling back to logistic regression"

            def base_builder() -> Pipeline:
                return build_logistic()

            param_grid = {"clf__C": [0.1, 1.0, 10.0]}
        else:
            implementation = "lightgbm.LGBMClassifier"

            def base_builder() -> object:
                return LGBMClassifier(
                    n_estimators=300,
                    learning_rate=0.05,
                    num_leaves=31,
                    subsample=0.8,
                    colsample_bytree=0.8,
                    random_state=random_state,
                )

            param_grid = {"n_estimators": [200, 350], "num_leaves": [31, 63]}
    elif normalized == "catboost":
        if CatBoostClassifier is None:
            implementation = "sklearn.linear_model.LogisticRegression"
            notes = "catboost package not installed; falling back to logistic regression"

            def base_builder() -> Pipeline:
                return build_logistic()

            param_grid = {"clf__C": [0.1, 1.0, 5.0]}
        else:
            implementation = "catboost.CatBoostClassifier"

            def base_builder() -> object:
                return CatBoostClassifier(
                    depth=6,
                    learning_rate=0.05,
                    iterations=300,
                    loss_function="Logloss",
                    random_state=random_state,
                    verbose=False,
                )

            param_grid = {"depth": [4, 6], "learning_rate": [0.03, 0.06]}
    else:
        raise ValueError(f"Unknown model_type '{model_type}'. Expected lightgbm, xgboost, or catboost.")

    def builder() -> object:
        estimator = base_builder()
        if mode == "tune":
            estimator = GridSearchCV(
                estimator,
                param_grid,
                cv=3,
                scoring="roc_auc",
                n_jobs=1,
                refit=True,
            )
        return estimator

    return ModelSpec(
        name=normalized,
        builder=builder,
        implementation=implementation,
        notes=notes,
    )


def _predict_proba(model: object, X: pd.DataFrame | np.ndarray) -> np.ndarray:
    if hasattr(model, "predict_proba"):
        proba = model.predict_proba(X)
        if isinstance(proba, list):
            proba = np.asarray(proba)
        if proba.ndim == 2 and proba.shape[1] == 2:
            return proba[:, 1]
        if proba.ndim == 1:
            return proba
    if hasattr(model, "decision_function"):
        scores = model.decision_function(X)
        return 1 / (1 + np.exp(-scores))
    raise AttributeError("Model does not provide predict_proba or decision_function")


def train_and_evaluate(
    train_df: pd.DataFrame,
    validation_df: pd.DataFrame,
    *,
    feature_columns: Sequence[str],
    target_column: str,
    random_state: int,
    calibration_bins: int,
    model_type: str,
    mode: str,
) -> list[EvaluationResult]:
    X_train = train_df[feature_columns]
    y_train = train_df[target_column].astype(int)
    X_val = validation_df[feature_columns]
    y_val = validation_df[target_column].astype(int)

    spec = choose_model(model_type, random_state=random_state, mode=mode)
    model = spec.builder()
    model.fit(X_train, y_train)
    y_score = _predict_proba(model, X_val)
    y_score = np.clip(y_score, 1e-9, 1 - 1e-9)
    roc_auc = float(roc_auc_score(y_val, y_score))
    avg_precision = float(average_precision_score(y_val, y_score))
    pr_precision, pr_recall, _ = precision_recall_curve(y_val, y_score)
    brier = float(brier_score_loss(y_val, y_score))
    logloss = float(log_loss(y_val, y_score))
    accuracy = float(accuracy_score(y_val, (y_score >= 0.5).astype(int)))
    prob_true, prob_pred = calibration_curve(y_val, y_score, n_bins=calibration_bins, strategy="quantile")

    metrics = {
        "roc_auc": roc_auc,
        "average_precision": avg_precision,
        "brier_score": brier,
        "log_loss": logloss,
        "accuracy": accuracy,
        "calibration_true": prob_true.tolist(),
        "calibration_pred": prob_pred.tolist(),
        "precision_curve": pr_precision.tolist(),
        "recall_curve": pr_recall.tolist(),
    }

    return [
        EvaluationResult(
            model_name=spec.name,
            implementation=spec.implementation,
            notes=spec.notes,
            metrics=metrics,
            y_true=y_val.to_numpy(),
            y_score=y_score,
        )
    ]


def _plot_roc(results: Sequence[EvaluationResult], path: Path) -> None:
    plt.figure(figsize=(8, 6))
    for result in results:
        fpr, tpr, _ = roc_curve(result.y_true, result.y_score)
        plt.plot(fpr, tpr, label=f"{result.model_name} (AUC={result.metrics['roc_auc']:.3f})")
    plt.plot([0, 1], [0, 1], linestyle="--", color="grey")
    plt.xlabel("False Positive Rate")
    plt.ylabel("True Positive Rate")
    plt.title("ROC Curve")
    plt.legend()
    plt.tight_layout()
    plt.savefig(path)
    plt.close()


def _plot_pr(results: Sequence[EvaluationResult], path: Path) -> None:
    plt.figure(figsize=(8, 6))
    for result in results:
        precision = np.asarray(result.metrics["precision_curve"])
        recall = np.asarray(result.metrics["recall_curve"])
        plt.plot(recall, precision, label=f"{result.model_name} (AP={result.metrics['average_precision']:.3f})")
    plt.xlabel("Recall")
    plt.ylabel("Precision")
    plt.title("Precision-Recall Curve")
    plt.legend()
    plt.tight_layout()
    plt.savefig(path)
    plt.close()


def _plot_calibration(results: Sequence[EvaluationResult], path: Path) -> None:
    plt.figure(figsize=(8, 6))
    for result in results:
        plt.plot(
            result.metrics["calibration_pred"],
            result.metrics["calibration_true"],
            marker="o",
            label=result.model_name,
        )
    plt.plot([0, 1], [0, 1], linestyle="--", color="grey")
    plt.xlabel("Predicted Probability")
    plt.ylabel("Observed Frequency")
    plt.title("Calibration Curve")
    plt.legend()
    plt.tight_layout()
    plt.savefig(path)
    plt.close()


def write_metrics_json(
    results: Sequence[EvaluationResult],
    config: InsiderBacktestConfig,
    path: Path,
) -> None:
    config_dict = asdict(config)
    for key, value in list(config_dict.items()):
        if isinstance(value, Path):
            config_dict[key] = str(value)
    payload = {
        "generated_at": datetime.utcnow().isoformat(),
        "config": config_dict,
        "models": [
            {
                "name": result.model_name,
                "implementation": result.implementation,
                "notes": result.notes,
                "metrics": {k: v for k, v in result.metrics.items() if isinstance(v, (float, int, list))},
            }
            for result in results
        ],
    }
    path.write_text(json.dumps(payload, indent=2))


@flow(name="insider-prefiling-classifier-backtest")
def insider_prefiling_backtest(config: InsiderBacktestConfig) -> BacktestArtifacts:
    """Run the insider pre-filing classifier backtest."""

    logger = get_run_logger()
    logger.info("Loading datasets: windows=%s filings=%s", config.windows_path, config.filings_path)
    windows = load_table(config.windows_path)
    filings = load_table(config.filings_path)

    labeled = build_labels(
        windows,
        filings,
        symbol_column=config.window_symbol_column,
        window_end_column=config.window_end_column,
        filing_symbol_column=config.filing_symbol_column,
        filing_date_column=config.filing_date_column,
        horizon_days=config.label_horizon_days,
    )

    feature_columns = _select_feature_columns(
        labeled,
        exclude={
            config.window_symbol_column,
            config.window_end_column,
            config.filing_symbol_column,
            config.filing_date_column,
            "label",
            "days_until_filing",
        },
    )

    train_idx, val_idx = time_based_split(
        labeled,
        time_column=config.window_end_column,
        validation_fraction=config.validation_fraction,
    )
    train_df = labeled.loc[train_idx]
    validation_df = labeled.loc[val_idx]

    logger.info(
        "Training on %d samples, validating on %d samples", len(train_df), len(validation_df)
    )
    logger.info("Using model=%s mode=%s", config.model, config.mode)

    results = train_and_evaluate(
        train_df,
        validation_df,
        feature_columns=feature_columns,
        target_column="label",
        random_state=config.random_state,
        calibration_bins=config.calibration_bins,
        model_type=config.model,
        mode=config.mode,
    )

    report_dir = config.report_dir.expanduser().resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    metrics_path = report_dir / f"insider_prefiling_metrics_{timestamp}.json"
    roc_path = report_dir / f"insider_prefiling_roc_{timestamp}.png"
    pr_path = report_dir / f"insider_prefiling_pr_{timestamp}.png"
    calibration_path = report_dir / f"insider_prefiling_calibration_{timestamp}.png"

    write_metrics_json(results, config, metrics_path)
    _plot_roc(results, roc_path)
    _plot_pr(results, pr_path)
    _plot_calibration(results, calibration_path)

    logger.info("Metrics written to %s", metrics_path)
    return BacktestArtifacts(
        metrics_path=metrics_path,
        roc_curve_path=roc_path,
        pr_curve_path=pr_path,
        calibration_path=calibration_path,
    )


__all__ = [
    "insider_prefiling_backtest",
    "InsiderBacktestConfig",
    "BacktestArtifacts",
    "choose_model",
    "train_and_evaluate",
]


def _build_arg_parser() -> argparse.ArgumentParser:
    """Return an argument parser exposing the backtest configuration knobs."""

    parser = argparse.ArgumentParser(description=__doc__ or "Run the insider pre-filing backtest")
    parser.add_argument("--windows", required=True, help="Path to the feature window dataset (CSV or Parquet)")
    parser.add_argument("--filings", required=True, help="Path to the Form 4 filings dataset (CSV or Parquet)")
    parser.add_argument("--label-horizon", type=int, default=5, help="Lookahead horizon in days for positive labels")
    parser.add_argument(
        "--validation-fraction",
        type=float,
        default=0.2,
        help="Fraction of data reserved for validation",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=Path("reports/backtests"),
        help="Directory to store generated metrics and plots",
    )
    parser.add_argument("--random-state", type=int, default=42, help="Random seed for model training")
    parser.add_argument("--calibration-bins", type=int, default=10, help="Number of bins for calibration curves")
    parser.add_argument(
        "--model",
        choices=["lightgbm", "xgboost", "catboost"],
        default="lightgbm",
        help="Model to train",
    )
    parser.add_argument(
        "--mode",
        choices=["train", "tune"],
        default="train",
        help="Execution mode: standard training or hyperparameter tuning",
    )
    return parser


def _main() -> None:
    args = _build_arg_parser().parse_args()
    config = InsiderBacktestConfig(
        windows_path=Path(args.windows),
        filings_path=Path(args.filings),
        label_horizon_days=args.label_horizon,
        validation_fraction=args.validation_fraction,
        report_dir=args.report_dir,
        random_state=args.random_state,
        calibration_bins=args.calibration_bins,
        model=args.model,
        mode=args.mode,
    )
    artifacts = insider_prefiling_backtest(config)
    print(
        json.dumps(
            {
                "metrics_path": str(artifacts.metrics_path),
                "roc_curve_path": str(artifacts.roc_curve_path),
                "pr_curve_path": str(artifacts.pr_curve_path),
                "calibration_path": str(artifacts.calibration_path),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    _main()
