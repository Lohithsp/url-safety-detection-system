"""Re-evaluate the persisted best model on the saved test split."""

from __future__ import annotations

import joblib
from sklearn.metrics import accuracy_score, classification_report, f1_score, precision_score, recall_score, roc_auc_score

from train import _proba


def evaluate_saved_model() -> dict:
    bundle = joblib.load("models/best_url_model.joblib")
    test_data = joblib.load("models/test_data.joblib")
    model = bundle["model"]
    X_test = test_data["X_test"]
    y_test = test_data["y_test"]
    pred = model.predict(X_test)
    prob = _proba(model, X_test)
    metrics = {
        "model": bundle["model_name"],
        "accuracy": accuracy_score(y_test, pred),
        "precision": precision_score(y_test, pred, zero_division=0),
        "recall": recall_score(y_test, pred, zero_division=0),
        "f1": f1_score(y_test, pred, zero_division=0),
        "roc_auc": roc_auc_score(y_test, prob),
        "classification_report": classification_report(y_test, pred, target_names=["Safe", "Malicious"]),
    }
    return metrics


if __name__ == "__main__":
    for key, value in evaluate_saved_model().items():
        print(f"{key}:")
        print(value)
