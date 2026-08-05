"""Dataset inspection, preprocessing, feature engineering, and reporting."""

from __future__ import annotations

import json
import os
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from ml_features import extract_url_features, features_from_dataframe, normalize_url, url_risk_score


ROOT = Path(__file__).resolve().parent
DATA_DIRS = [ROOT / "data", ROOT / "dataset for url"]
REPORT_DIR = ROOT / "reports"
VIZ_DIR = ROOT / "visualizations"
MODEL_DIR = ROOT / "models"

LABEL_CANDIDATES = ("label", "target", "class", "phishing", "malicious", "result", "status", "type")


def ensure_dirs() -> None:
    for path in (ROOT / "data", MODEL_DIR, REPORT_DIR, VIZ_DIR, ROOT / "database"):
        path.mkdir(exist_ok=True)


def discover_csv_files() -> list[Path]:
    files: list[Path] = []
    for directory in DATA_DIRS:
        if directory.exists():
            files.extend(sorted(directory.glob("*.csv")))
    return files


def read_csv(path: Path) -> pd.DataFrame:
    max_rows = int(os.getenv("URL_ML_MAX_ROWS", "5000") or "5000")
    df = pd.read_csv(path, encoding_errors="replace")
    if max_rows and len(df) > max_rows:
        return df.sample(n=max_rows, random_state=42).reset_index(drop=True)
    return df


def detect_label_column(df: pd.DataFrame) -> str:
    normalized = {c.lower().strip(): c for c in df.columns}
    for candidate in LABEL_CANDIDATES:
        if candidate in normalized:
            return normalized[candidate]
    binary_cols = [
        c for c in df.columns
        if df[c].nunique(dropna=True) == 2 and not pd.api.types.is_float_dtype(df[c])
    ]
    if len(binary_cols) == 1:
        return binary_cols[0]
    raise ValueError(f"Could not identify a label column. Columns: {list(df.columns)}")


def normalize_labels(df: pd.DataFrame, label_col: str) -> tuple[pd.Series, dict]:
    raw = df[label_col]
    lower_name = label_col.lower()
    if raw.dtype == object:
        text = raw.astype(str).str.lower().str.strip()
        malicious_values = {"1", "malicious", "phishing", "bad", "unsafe", "yes", "true"}
        safe_values = {"0", "safe", "legitimate", "benign", "good", "no", "false"}
        if set(text.dropna().unique()).issubset(malicious_values | safe_values):
            y = text.isin(malicious_values).astype(int)
            return y, {"strategy": "semantic_string_values", "malicious_values": sorted(malicious_values)}

    numeric = pd.to_numeric(raw, errors="coerce")
    values = sorted(v for v in numeric.dropna().unique().tolist())
    if len(values) != 2:
        raise ValueError(f"Label column {label_col} must be binary after validation; found {values}")

    if any(word in lower_name for word in ("phishing", "malicious", "unsafe", "bad")):
        malicious_value = 1 if 1 in values else max(values)
        return (numeric == malicious_value).astype(int), {
            "strategy": "label_name_semantics",
            "malicious_raw_value": malicious_value,
        }

    url_col = next((c for c in df.columns if c.lower() in {"url", "link"}), None)
    if url_col:
        risk_by_value = {
            value: df.loc[numeric == value, url_col].astype(str).map(url_risk_score).mean()
            for value in values
        }
        malicious_value = max(risk_by_value, key=risk_by_value.get)
        return (numeric == malicious_value).astype(int), {
            "strategy": "url_risk_signal_orientation",
            "malicious_raw_value": malicious_value,
            "risk_by_raw_value": risk_by_value,
        }

    malicious_value = max(values)
    return (numeric == malicious_value).astype(int), {
        "strategy": "numeric_default_high_value_is_malicious",
        "malicious_raw_value": malicious_value,
    }


def inspect_dataset(path: Path) -> dict:
    df = read_csv(path)
    label_col = detect_label_column(df)
    y, label_info = normalize_labels(df, label_col)
    report = {
        "file": str(path),
        "rows": int(df.shape[0]),
        "columns": int(df.shape[1]),
        "column_names": list(df.columns),
        "label_column": label_col,
        "target_variable": "is_malicious (1=malicious, 0=safe)",
        "feature_columns": [c for c in df.columns if c != label_col],
        "missing_values": {k: int(v) for k, v in df.isna().sum().items() if int(v) > 0},
        "duplicate_rows": int(df.duplicated().sum()),
        "raw_class_distribution": {str(k): int(v) for k, v in df[label_col].value_counts(dropna=False).items()},
        "normalized_class_distribution": {str(k): int(v) for k, v in y.value_counts().items()},
        "label_normalization": label_info,
    }
    return report


def build_preprocessed_dataset() -> tuple[pd.DataFrame, pd.Series, dict]:
    ensure_dirs()
    csv_files = discover_csv_files()
    if not csv_files:
        raise FileNotFoundError("No CSV files found in data/ or dataset for url/.")

    frames: list[pd.DataFrame] = []
    reports: list[dict] = []
    for path in csv_files:
        df = read_csv(path)
        label_col = detect_label_column(df)
        y, label_info = normalize_labels(df, label_col)
        url_col = next((c for c in df.columns if c.lower() in {"url", "link"}), None)
        item = inspect_dataset(path)
        item["label_normalization"] = label_info
        if not url_col:
            item["used_for_training"] = False
            item["exclusion_reason"] = (
                "No raw URL column is available. The dataset is inspected and reported, "
                "but excluded from live scanner training because user scans can only "
                "extract features from a submitted URL."
            )
            reports.append(item)
            continue

        X = features_from_dataframe(df)
        if os.getenv("URL_ML_AUGMENT_SAFE", "1") != "0":
            safe_urls = df.loc[y.values == 0, url_col].dropna().astype(str).drop_duplicates().head(5000)
            augmented_urls = []
            for raw_url in safe_urls:
                base = normalize_url(raw_url).rstrip("/")
                augmented_urls.extend([
                    f"{base}/about",
                    f"{base}/search?q=security",
                    f"{base}/products?id=1",
                    f"{base}/share/6a2226fe-3e9c-8321-91ef-0c9384ecb483",
                    f"{base}/indiacampus/#/",
                    f"{base}/wp-content/uploads/2026/06/photo.jpg",
                    f"{base}/blog/news-update-2026",
                    f"{base}/dashboard/home?user=123&session=abc",
                ])
            if augmented_urls:
                augmented_X = pd.DataFrame([extract_url_features(url) for url in augmented_urls])
                X = pd.concat([X, augmented_X], ignore_index=True)
                y = pd.concat([pd.Series(y).reset_index(drop=True), pd.Series([0] * len(augmented_X))], ignore_index=True)

        combined = X.copy()
        combined["is_malicious"] = y.values
        before = len(combined)
        # combined = combined.drop_duplicates()
        frames.append(combined)

        item["used_for_training"] = True
        item["engineered_feature_columns"] = list(X.columns)
        item["duplicates_removed_after_feature_engineering"] = 0
        reports.append(item)

    if not frames:
        raise ValueError("No training-ready CSV files contain a raw URL column.")

    full = pd.concat(frames, ignore_index=True)
    before_all = len(full)
    # full = full.drop_duplicates()
    y = full.pop("is_malicious").astype(int)
    X = full.apply(pd.to_numeric, errors="coerce")

    missing = X.isna().sum()
    class_counts = y.value_counts().to_dict()
    imbalance_ratio = max(class_counts.values()) / max(min(class_counts.values()), 1)
    constant_features = [c for c in X.columns if X[c].nunique(dropna=True) <= 1]
    X = X.drop(columns=constant_features)

    report = {
        "datasets": reports,
        "combination_strategy": (
            "All CSV files are inspected independently, labels are normalized to "
            "1=malicious. Training uses datasets that contain a raw URL column and "
            "therefore support the same URL-extractable feature space used during "
            "live user scans. Datasets without raw URLs are reported but excluded "
            "from live-model training to avoid incompatible feature definitions."
        ),
        "total_rows_after_combining": int(len(X)),
        "duplicate_rows_removed_after_combining": int(before_all - len(X)),
        "selected_features": list(X.columns),
        "removed_constant_features": constant_features,
        "missing_values_after_engineering": {k: int(v) for k, v in missing.items() if int(v) > 0},
        "class_distribution": {str(k): int(v) for k, v in class_counts.items()},
        "class_balancing_strategy": (
            "Use class_weight/sample_weight during training"
            if imbalance_ratio > 1.2 else "No balancing required"
        ),
        "imbalance_ratio": imbalance_ratio,
    }
    save_preprocessing_report(report, X, y)
    return X, y, report


def save_preprocessing_report(report: dict, X: pd.DataFrame, y: pd.Series) -> None:
    ensure_dirs()
    (REPORT_DIR / "preprocessing_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = [
        "# Preprocessing Report",
        "",
        f"Total rows after combining: {report['total_rows_after_combining']}",
        f"Target variable: `is_malicious` where `1=malicious`, `0=safe`.",
        f"Selected features: {len(report['selected_features'])}",
        f"Class distribution: {report['class_distribution']}",
        f"Class balancing: {report['class_balancing_strategy']}",
        "",
        "## Dataset Inspection",
    ]
    for item in report["datasets"]:
        lines.extend([
            f"### {Path(item['file']).name}",
            f"- Rows: {item['rows']}",
            f"- Columns: {item['columns']}",
            f"- Label column: {item['label_column']}",
            f"- Duplicate rows: {item['duplicate_rows']}",
            f"- Raw class distribution: {item['raw_class_distribution']}",
            f"- Normalized class distribution: {item['normalized_class_distribution']}",
        ])
    (REPORT_DIR / "preprocessing_report.md").write_text("\n".join(lines), encoding="utf-8")

    plt.figure(figsize=(7, 4))
    sns.countplot(x=y.map({0: "Safe", 1: "Malicious"}))
    plt.title("Combined Dataset Class Distribution")
    plt.xlabel("Class")
    plt.ylabel("Rows")
    plt.tight_layout()
    plt.savefig(VIZ_DIR / "dataset_class_distribution.png", dpi=160)
    plt.close()

    top_features = X.var(numeric_only=True).sort_values(ascending=False).head(15)
    plt.figure(figsize=(9, 5))
    sns.barplot(x=top_features.values, y=top_features.index)
    plt.title("Top Engineered Feature Variance")
    plt.xlabel("Variance")
    plt.ylabel("Feature")
    plt.tight_layout()
    plt.savefig(VIZ_DIR / "dataset_feature_distribution.png", dpi=160)
    plt.close()


if __name__ == "__main__":
    X_data, y_data, preprocessing_report = build_preprocessed_dataset()
    print(f"Prepared {len(X_data)} rows with {X_data.shape[1]} features.")
    print(f"Reports saved to {REPORT_DIR}")
