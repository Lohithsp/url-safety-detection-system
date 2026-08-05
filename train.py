"""Train, compare, select, and persist URL safety ML models."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.ensemble import ExtraTreesClassifier, GradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_sample_weight

from explain import save_explainability_artifacts
from preprocess import MODEL_DIR, REPORT_DIR, VIZ_DIR, build_preprocessed_dataset, ensure_dirs

try:
    from xgboost import XGBClassifier
except Exception:
    XGBClassifier = None


RANDOM_STATE = 42


def _models() -> dict:
    models = {
        "Random Forest": RandomForestClassifier(
            n_estimators=300,
            random_state=RANDOM_STATE,
            class_weight="balanced",
            n_jobs=-1,
            max_depth=None,
        ),
        "Extra Trees": ExtraTreesClassifier(
            n_estimators=300,
            random_state=RANDOM_STATE,
            class_weight="balanced",
            n_jobs=-1,
        ),
        "Gradient Boosting": GradientBoostingClassifier(random_state=RANDOM_STATE),
        "Logistic Regression": LogisticRegression(
            max_iter=2000,
            class_weight="balanced",
        ),
    }
    if XGBClassifier is not None:
        models["XGBoost"] = XGBClassifier(
            n_estimators=300,
            max_depth=6,
            learning_rate=0.08,
            subsample=0.9,
            colsample_bytree=0.9,
            objective="binary:logistic",
            eval_metric="logloss",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        )
    return models


def _pipeline(name: str, estimator) -> Pipeline:
    steps = [("imputer", SimpleImputer(strategy="median"))]
    if name == "Logistic Regression":
        steps.append(("scaler", StandardScaler()))
    steps.append(("model", estimator))
    return Pipeline(steps)


def _proba(model: Pipeline, X: pd.DataFrame) -> np.ndarray:
    if hasattr(model, "predict_proba"):
        return model.predict_proba(X)[:, 1]
    scores = model.decision_function(X)
    return (scores - scores.min()) / max(scores.max() - scores.min(), 1e-9)


def train_all() -> dict:
    ensure_dirs()
    X, y, preprocessing_report = build_preprocessed_dataset()
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y
    )
    sample_weight = compute_sample_weight(class_weight="balanced", y=y_train)

    results = []
    fitted = {}
    roc_data = {}
    for name, estimator in _models().items():
        pipe = _pipeline(name, estimator)
        fit_kwargs = {}
        if name in {"Gradient Boosting", "XGBoost"}:
            fit_kwargs["model__sample_weight"] = sample_weight
        pipe.fit(X_train, y_train, **fit_kwargs)
        pred = pipe.predict(X_test)
        prob = _proba(pipe, X_test)
        metrics = {
            "model": name,
            "accuracy": accuracy_score(y_test, pred),
            "precision": precision_score(y_test, pred, zero_division=0),
            "recall": recall_score(y_test, pred, zero_division=0),
            "f1": f1_score(y_test, pred, zero_division=0),
            "roc_auc": roc_auc_score(y_test, prob),
        }
        results.append(metrics)
        fitted[name] = pipe
        roc_data[name] = roc_curve(y_test, prob)

    comparison = pd.DataFrame(results).sort_values(
        ["f1", "roc_auc", "recall"], ascending=False
    )
    best_name = str(comparison.iloc[0]["model"])
    best_model = fitted[best_name]
    best_pred = best_model.predict(X_test)
    best_prob = _proba(best_model, X_test)

    bundle = {
        "model": best_model,
        "model_name": best_name,
        "primary_model": "Random Forest",
        "feature_names": list(X.columns),
        "target": "is_malicious",
        "label_mapping": {"safe": 0, "malicious": 1},
        "preprocessing_report": preprocessing_report,
        "metrics": comparison.to_dict(orient="records"),
    }
    joblib.dump(bundle, MODEL_DIR / "best_url_model.joblib")
    joblib.dump({"X_test": X_test, "y_test": y_test}, MODEL_DIR / "test_data.joblib")

    save_evaluation_artifacts(comparison, y_test, best_pred, best_prob, roc_data, best_name)
    save_explainability_artifacts(best_model, X_train, list(X.columns), best_name)
    return {
        "best_model": best_name,
        "comparison": comparison,
        "model_path": str(MODEL_DIR / "best_url_model.joblib"),
    }


def save_evaluation_artifacts(
    comparison: pd.DataFrame,
    y_test: pd.Series,
    best_pred: np.ndarray,
    best_prob: np.ndarray,
    roc_data: dict,
    best_name: str,
) -> None:
    comparison.to_csv(REPORT_DIR / "model_comparison.csv", index=False)
    markdown = ["| " + " | ".join(comparison.columns) + " |"]
    markdown.append("| " + " | ".join(["---"] * len(comparison.columns)) + " |")
    for _, row in comparison.iterrows():
        markdown.append("| " + " | ".join(str(round(v, 5)) if isinstance(v, float) else str(v) for v in row) + " |")
    (REPORT_DIR / "model_comparison.md").write_text("\n".join(markdown), encoding="utf-8")
    (REPORT_DIR / "classification_report.txt").write_text(
        classification_report(y_test, best_pred, target_names=["Safe", "Malicious"]),
        encoding="utf-8",
    )
    summary = {
        "best_model": best_name,
        "selection_rule": "Highest F1, then ROC-AUC, then recall.",
        "metrics": comparison.to_dict(orient="records"),
    }
    (REPORT_DIR / "model_training_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    cm = confusion_matrix(y_test, best_pred)
    plt.figure(figsize=(5, 4))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", xticklabels=["Safe", "Malicious"], yticklabels=["Safe", "Malicious"])
    plt.title(f"Confusion Matrix - {best_name}")
    plt.xlabel("Predicted")
    plt.ylabel("Actual")
    plt.tight_layout()
    plt.savefig(VIZ_DIR / "confusion_matrix.png", dpi=160)
    plt.close()

    plt.figure(figsize=(7, 5))
    for name, (fpr, tpr, _) in roc_data.items():
        plt.plot(fpr, tpr, label=name)
    plt.plot([0, 1], [0, 1], "k--", alpha=0.5)
    plt.title("ROC Curves")
    plt.xlabel("False Positive Rate")
    plt.ylabel("True Positive Rate")
    plt.legend()
    plt.tight_layout()
    plt.savefig(VIZ_DIR / "roc_curves.png", dpi=160)
    plt.close()


if __name__ == "__main__":
    result = train_all()
    print(f"Best model: {result['best_model']}")
    print(f"Saved model: {result['model_path']}")
