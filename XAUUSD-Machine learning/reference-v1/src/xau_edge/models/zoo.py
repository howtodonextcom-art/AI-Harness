"""The four benchmark models with fixed, modest hyperparameters (chosen a priori, not tuned).

Order follows the brief: logistic regression, random forest, XGBoost, LightGBM. Deep models are
deliberately absent. Missing values (warm-up, undefined ratios) are imputed with the training median
for the linear and forest models; the boosters handle them natively.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Final

from lightgbm import LGBMClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from xau_edge.models.walkforward import Classifier

SEED: Final = 7

HYPERPARAMETERS: Final[dict[str, dict[str, Any]]] = {
    "logistic": {"C": 0.1, "max_iter": 500, "imputer": "median", "scaler": "standard"},
    "random_forest": {
        "n_estimators": 200,
        "max_depth": 6,
        "min_samples_leaf": 50,
        "imputer": "median",
        "random_state": SEED,
    },
    "xgboost": {
        "n_estimators": 200,
        "max_depth": 3,
        "learning_rate": 0.05,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "min_child_weight": 20,
        "random_state": SEED,
    },
    "lightgbm": {
        "n_estimators": 200,
        "num_leaves": 8,
        "learning_rate": 0.05,
        "subsample": 0.8,
        "subsample_freq": 1,
        "colsample_bytree": 0.8,
        "min_child_samples": 50,
        "random_state": SEED,
    },
}


def _logistic() -> Classifier:
    h = HYPERPARAMETERS["logistic"]
    return Pipeline(  # type: ignore[no-any-return]
        [
            ("impute", SimpleImputer(strategy="median", keep_empty_features=True)),
            ("scale", StandardScaler()),
            ("model", LogisticRegression(C=h["C"], max_iter=h["max_iter"])),
        ]
    )


def _forest() -> Classifier:
    h = HYPERPARAMETERS["random_forest"]
    return Pipeline(  # type: ignore[no-any-return]
        [
            ("impute", SimpleImputer(strategy="median", keep_empty_features=True)),
            (
                "model",
                RandomForestClassifier(
                    n_estimators=h["n_estimators"],
                    max_depth=h["max_depth"],
                    min_samples_leaf=h["min_samples_leaf"],
                    random_state=h["random_state"],
                    n_jobs=1,
                ),
            ),
        ]
    )


def _xgboost() -> Classifier:
    h = HYPERPARAMETERS["xgboost"]
    return XGBClassifier(
        n_estimators=h["n_estimators"],
        max_depth=h["max_depth"],
        learning_rate=h["learning_rate"],
        subsample=h["subsample"],
        colsample_bytree=h["colsample_bytree"],
        min_child_weight=h["min_child_weight"],
        objective="multi:softprob",
        tree_method="hist",
        random_state=h["random_state"],
        n_jobs=1,
        verbosity=0,
    )


def _lightgbm() -> Classifier:
    h = HYPERPARAMETERS["lightgbm"]
    return LGBMClassifier(
        n_estimators=h["n_estimators"],
        num_leaves=h["num_leaves"],
        learning_rate=h["learning_rate"],
        subsample=h["subsample"],
        subsample_freq=h["subsample_freq"],
        colsample_bytree=h["colsample_bytree"],
        min_child_samples=h["min_child_samples"],
        random_state=h["random_state"],
        n_jobs=1,
        verbose=-1,
    )


MODELS: Final[dict[str, Callable[[], Classifier]]] = {
    "logistic": _logistic,
    "random_forest": _forest,
    "xgboost": _xgboost,
    "lightgbm": _lightgbm,
}
