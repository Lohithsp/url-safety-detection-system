"""Explainable AI utilities for URL safety predictions."""

from __future__ import annotations

from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from ml_features import FEATURE_NAMES, extract_url_features, human_feature_reason


ROOT = Path(__file__).resolve().parent
MODEL_PATH = ROOT / "models" / "best_url_model.joblib"
VIZ_DIR = ROOT / "visualizations"


def _estimator_from_pipeline(model):
    return model.named_steps.get("model") if hasattr(model, "named_steps") else model


def _transform_for_model(model, X: pd.DataFrame) -> np.ndarray:
    if hasattr(model, "named_steps"):
        steps = list(model.named_steps.items())[:-1]
        transformed = X
        for _, step in steps:
            transformed = step.transform(transformed)
        return transformed
    return X.values


def save_explainability_artifacts(model, X_train: pd.DataFrame, feature_names: list[str], model_name: str) -> None:
    VIZ_DIR.mkdir(exist_ok=True)
    estimator = _estimator_from_pipeline(model)
    if hasattr(estimator, "feature_importances_"):
        importance = pd.DataFrame({
            "feature": feature_names,
            "importance": estimator.feature_importances_,
        }).sort_values("importance", ascending=False)
        importance.to_csv(ROOT / "reports" / "feature_importance.csv", index=False)

        plt.figure(figsize=(9, 6))
        sns.barplot(data=importance.head(20), x="importance", y="feature")
        plt.title(f"Feature Importance - {model_name}")
        plt.tight_layout()
        plt.savefig(VIZ_DIR / "feature_importance.png", dpi=160)
        plt.close()

    try:
        import shap

        sample = X_train.sample(min(1000, len(X_train)), random_state=42)
        transformed = _transform_for_model(model, sample)
        explainer = shap.TreeExplainer(estimator)
        shap_values = explainer.shap_values(transformed)
        if isinstance(shap_values, list):
            shap_values = shap_values[1]
        if getattr(shap_values, "ndim", 2) == 3:
            shap_values = shap_values[:, :, 1]
        shap.summary_plot(shap_values, transformed, feature_names=feature_names, show=False)
        plt.tight_layout()
        plt.savefig(VIZ_DIR / "shap_summary.png", dpi=160, bbox_inches="tight")
        plt.close()
    except Exception as exc:
        (ROOT / "reports" / "shap_warning.txt").write_text(
            f"SHAP summary plot could not be generated: {exc}", encoding="utf-8"
        )


_MODEL_CACHE = None
_EXPLAINER_CACHE = None

def get_model_bundle():
    global _MODEL_CACHE
    if _MODEL_CACHE is None:
        _MODEL_CACHE = joblib.load(MODEL_PATH)
    return _MODEL_CACHE

def get_shap_explainer(estimator):
    global _EXPLAINER_CACHE
    if _EXPLAINER_CACHE is None:
        import shap
        _EXPLAINER_CACHE = shap.TreeExplainer(estimator)
    return _EXPLAINER_CACHE


def explain_url(url: str, top_n: int = 5) -> dict:
    bundle = get_model_bundle()
    model = bundle["model"]
    feature_names = bundle.get("feature_names", FEATURE_NAMES)
    X = pd.DataFrame([extract_url_features(url)]).reindex(columns=feature_names)
    probability = float(model.predict_proba(X)[0, 1])
    prediction = "Malicious" if probability >= 0.5 else "Safe"

    contributions = []
    try:
        estimator = _estimator_from_pipeline(model)
        transformed = _transform_for_model(model, X)
        explainer = get_shap_explainer(estimator)
        values = explainer.shap_values(transformed)
        if isinstance(values, list):
            values = values[1]
        if getattr(values, "ndim", 2) == 3:
            values = values[:, :, 1]
        row_values = np.asarray(values)[0]
        contributions = sorted(
            zip(feature_names, row_values, X.iloc[0].values),
            key=lambda item: abs(item[1]),
            reverse=True,
        )
    except Exception:
        estimator = _estimator_from_pipeline(model)
        if hasattr(estimator, "feature_importances_"):
            contributions = sorted(
                zip(feature_names, estimator.feature_importances_, X.iloc[0].values),
                key=lambda item: abs(item[1]),
                reverse=True,
            )

    reasons = _rule_reasons(X.iloc[0], malicious=prediction == "Malicious")
    for feature, value, raw_value in contributions:
        if len(reasons) >= top_n:
            break
        if prediction == "Malicious" and feature == "is_https":
            continue
        if prediction == "Malicious" and value > 0:
            reason = human_feature_reason(feature, raw_value, "high")
        elif prediction == "Safe" and value < 0:
            reason = human_feature_reason(feature, raw_value, "low")
        else:
            continue
        if reason not in reasons:
            reasons.append(reason)

    if not reasons:
        reasons = ["Normal URL structure", "Low-risk feature profile"] if prediction == "Safe" else ["Abnormal URL feature profile"]

    return {
        "prediction": prediction,
        "confidence": round(max(probability, 1 - probability) * 100, 2),
        "malicious_probability": round(probability * 100, 2),
        "risk_level": risk_level(probability),
        "reasons": reasons[:top_n],
        "feature_values": {k: float(v) for k, v in X.iloc[0].items()},
    }


def _rule_reasons(row: pd.Series, malicious: bool) -> list[str]:
    if not malicious:
        reasons = []
        if row.get("is_https", 0) == 1:
            reasons.append("Normal HTTPS URL structure")
        if row.get("has_suspicious_keyword", 0) == 0:
            reasons.append("No suspicious keywords")
        if row.get("url_length", 0) < 80 and row.get("num_subdomains", 0) <= 1:
            reasons.append("Trusted feature patterns and low-risk URL length")
        return reasons

    checks = [
        ("has_suspicious_keyword", 0, "Contains suspicious keyword"),
        ("url_length", 100, "Unusually long URL"),
        ("special_char_count", 15, "Multiple special characters detected"),
        ("num_subdomains", 2, "Suspicious domain structure"),
        ("is_ip", 0, "Uses an IP address instead of a domain"),
        ("has_shortener", 0, "Uses a URL shortener"),
        ("num_at", 0, "Contains an at-sign that can hide the real destination"),
        ("redirect_keyword_count", 0, "Redirect-style parameters detected"),
        ("encoded_char_count", 0, "Encoded characters suggest obfuscation"),
    ]
    reasons = []
    for feature, threshold, label in checks:
        value = row.get(feature, 0)
        if value > threshold:
            reasons.append(label)
    return reasons


def risk_level(probability: float) -> str:
    if probability >= 0.85:
        return "High"
    if probability >= 0.5:
        return "Medium"
    return "Low"


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Explain a URL safety prediction.")
    parser.add_argument("url")
    args = parser.parse_args()
    print(explain_url(args.url))
