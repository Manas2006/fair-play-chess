from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    precision_recall_curve,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from fairplay.features import FEATURE_COLUMNS


@dataclass
class ModelBundle:
    pipeline: Pipeline
    feature_columns: list[str]
    metadata: dict[str, Any]

    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        return self.pipeline.predict_proba(frame[self.feature_columns])[:, 1]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)

    @classmethod
    def load(cls, path: Path) -> "ModelBundle":
        return joblib.load(path)


def _recall_at_fpr(y_true: np.ndarray, probabilities: np.ndarray, target_fpr: float) -> dict[str, float]:
    fpr, tpr, thresholds = roc_curve(y_true, probabilities)
    valid = np.where(fpr <= target_fpr)[0]
    index = int(valid[-1]) if len(valid) else 0
    threshold = float(thresholds[index])
    if not np.isfinite(threshold):
        threshold = 1.0
    return {
        "target_fpr": target_fpr,
        "observed_fpr": float(fpr[index]),
        "recall": float(tpr[index]),
        "threshold": threshold,
    }


def _expected_calibration_error(y_true: np.ndarray, probabilities: np.ndarray, bins: int = 10) -> float:
    boundaries = np.linspace(0, 1, bins + 1)
    total = len(y_true)
    ece = 0.0
    for lower, upper in zip(boundaries[:-1], boundaries[1:]):
        mask = (probabilities >= lower) & (probabilities < upper if upper < 1 else probabilities <= upper)
        if mask.any():
            ece += mask.mean() * abs(float(y_true[mask].mean()) - float(probabilities[mask].mean()))
    return float(ece if total else 0.0)


def train_model(
    features: pd.DataFrame,
    labels: pd.DataFrame,
    seed: int = 7,
) -> tuple[ModelBundle, pd.DataFrame, dict[str, Any]]:
    data = features.merge(labels[["account_id", "label", "assistance_rate"]], on="account_id", validate="one_to_one")
    train, test = train_test_split(
        data,
        test_size=0.25,
        random_state=seed,
        stratify=data["label"],
    )
    base = HistGradientBoostingClassifier(
        learning_rate=0.07,
        max_iter=180,
        max_leaf_nodes=15,
        min_samples_leaf=12,
        l2_regularization=0.8,
        random_state=seed,
    )
    calibrated = CalibratedClassifierCV(base, method="sigmoid", cv=4)
    pipeline = Pipeline([("scale", StandardScaler()), ("model", calibrated)])
    pipeline.fit(train[FEATURE_COLUMNS], train["label"])

    probabilities = pipeline.predict_proba(test[FEATURE_COLUMNS])[:, 1]
    y_test = test["label"].to_numpy()
    precision, recall, _ = precision_recall_curve(y_test, probabilities)
    metrics: dict[str, Any] = {
        "test_accounts": int(len(test)),
        "positive_accounts": int(y_test.sum()),
        "roc_auc": float(roc_auc_score(y_test, probabilities)),
        "pr_auc": float(average_precision_score(y_test, probabilities)),
        "brier_score": float(brier_score_loss(y_test, probabilities)),
        "ece_10_bin": _expected_calibration_error(y_test, probabilities),
        "recall_at_fpr": [
            _recall_at_fpr(y_test, probabilities, 0.01),
            _recall_at_fpr(y_test, probabilities, 0.001),
        ],
        "max_f1": float(np.max(2 * precision * recall / np.maximum(precision + recall, 1e-12))),
        "warning": "Synthetic benchmark only; not an estimate of real-world cheating prevalence or accuracy.",
    }
    scored = test.copy()
    scored["risk_score"] = probabilities
    scored["split"] = "test"
    all_scored = data.copy()
    all_scored["risk_score"] = pipeline.predict_proba(data[FEATURE_COLUMNS])[:, 1]
    all_scored["split"] = np.where(all_scored["account_id"].isin(test["account_id"]), "test", "train")
    bundle = ModelBundle(
        pipeline=pipeline,
        feature_columns=list(FEATURE_COLUMNS),
        metadata={"seed": seed, "metrics": metrics, "training_rows": len(train)},
    )
    return bundle, all_scored, metrics
