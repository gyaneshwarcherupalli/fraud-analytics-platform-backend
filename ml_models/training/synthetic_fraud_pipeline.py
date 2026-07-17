"""Generate synthetic fraud data, run EDA, and perform feature selection.

Usage:
    python ml_models/training/synthetic_fraud_pipeline.py --rows 25000 --top-k 20
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import VarianceThreshold, mutual_info_classif
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split


def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def generate_synthetic_fraud_dataset(rows: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    merchant_categories = np.array(
        [
            "groceries",
            "travel",
            "electronics",
            "food_delivery",
            "gaming",
            "fashion",
            "utilities",
            "healthcare",
            "fuel",
            "cash_withdrawal",
        ]
    )
    device_types = np.array(["mobile", "desktop", "tablet", "pos_terminal"])
    channels = np.array(["online", "in_store", "atm"])

    df = pd.DataFrame(
        {
            "transaction_id": [f"TXN-{i:08d}" for i in range(rows)],
            "customer_id": rng.integers(10_000, 99_999, size=rows).astype(str),
            "amount": np.round(rng.gamma(shape=2.0, scale=120.0, size=rows), 2),
            "hour": rng.integers(0, 24, size=rows),
            "day_of_week": rng.integers(0, 7, size=rows),
            "merchant_category": rng.choice(
                merchant_categories,
                size=rows,
                p=[0.21, 0.08, 0.11, 0.14, 0.09, 0.12, 0.1, 0.06, 0.07, 0.02],
            ),
            "device_type": rng.choice(device_types, size=rows, p=[0.52, 0.18, 0.1, 0.2]),
            "channel": rng.choice(channels, size=rows, p=[0.48, 0.44, 0.08]),
            "distance_from_home_km": np.round(rng.exponential(scale=15, size=rows), 2),
            "transaction_velocity_1h": rng.poisson(lam=2.2, size=rows),
            "account_age_days": rng.integers(1, 3650, size=rows),
            "avg_ticket_30d": np.round(rng.gamma(shape=2.5, scale=85.0, size=rows), 2),
            "is_international": rng.binomial(1, 0.12, size=rows),
            "has_chargeback_history": rng.binomial(1, 0.08, size=rows),
        }
    )

    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    df["is_night_txn"] = ((df["hour"] <= 5) | (df["hour"] >= 23)).astype(int)

    high_risk_category = df["merchant_category"].isin(
        ["travel", "electronics", "gaming", "cash_withdrawal"]
    )
    channel_risk = df["channel"].map({"online": 1.0, "in_store": 0.2, "atm": 0.8}).astype(float)

    # Build a probabilistic fraud score that mimics realistic risk factors.
    linear_score = (
        -4.3
        + 0.0048 * df["amount"]
        + 0.03 * df["distance_from_home_km"]
        + 0.26 * df["transaction_velocity_1h"]
        + 1.05 * df["is_international"]
        + 1.25 * df["has_chargeback_history"]
        + 0.45 * df["is_night_txn"]
        + 0.34 * high_risk_category.astype(int)
        + 0.40 * channel_risk
        + 0.0022 * (df["amount"] > (2.7 * df["avg_ticket_30d"]))
        - 0.00055 * df["account_age_days"]
    )

    probability = sigmoid(linear_score)
    df["is_fraud"] = rng.binomial(1, probability)

    # Inject a small number of missing values to make EDA realistic.
    missing_idx = rng.choice(rows, size=max(1, rows // 120), replace=False)
    df.loc[missing_idx, "distance_from_home_km"] = np.nan

    return df


def run_eda(df: pd.DataFrame, output_dir: Path) -> Dict[str, float]:
    output_dir.mkdir(parents=True, exist_ok=True)

    missing = df.isnull().sum().sort_values(ascending=False)
    numeric = df.select_dtypes(include=["number"])

    summary = {
        "rows": int(df.shape[0]),
        "columns": int(df.shape[1]),
        "fraud_rate": float(df["is_fraud"].mean()),
        "total_missing_cells": int(df.isnull().sum().sum()),
        "avg_amount": float(df["amount"].mean()),
        "median_amount": float(df["amount"].median()),
    }

    description = numeric.describe().T
    description.to_csv(output_dir / "numeric_summary.csv")

    corr = numeric.corr(numeric_only=True)
    corr.to_csv(output_dir / "correlation_matrix.csv")

    missing.to_csv(output_dir / "missing_values.csv", header=["missing_count"])

    with (output_dir / "eda_summary.md").open("w", encoding="utf-8") as f:
        f.write("# Synthetic Fraud Dataset EDA\n\n")
        f.write(f"- Rows: {summary['rows']}\n")
        f.write(f"- Columns: {summary['columns']}\n")
        f.write(f"- Fraud rate: {summary['fraud_rate']:.4f}\n")
        f.write(f"- Missing cells: {summary['total_missing_cells']}\n")
        f.write(f"- Average amount: {summary['avg_amount']:.2f}\n")
        f.write(f"- Median amount: {summary['median_amount']:.2f}\n\n")
        f.write("## Top Missing Columns\n")
        for col, val in missing.head(10).items():
            f.write(f"- {col}: {int(val)}\n")

    plt.figure(figsize=(6, 4))
    sns.countplot(x="is_fraud", data=df)
    plt.title("Fraud Class Distribution")
    plt.tight_layout()
    plt.savefig(output_dir / "fraud_distribution.png", dpi=140)
    plt.close()

    plt.figure(figsize=(8, 6))
    sns.heatmap(corr, cmap="RdBu_r", center=0)
    plt.title("Correlation Heatmap")
    plt.tight_layout()
    plt.savefig(output_dir / "correlation_heatmap.png", dpi=140)
    plt.close()

    plt.figure(figsize=(8, 4))
    sns.boxplot(x="is_fraud", y="amount", data=df)
    plt.title("Amount vs Fraud")
    plt.tight_layout()
    plt.savefig(output_dir / "amount_by_fraud.png", dpi=140)
    plt.close()

    return summary


def prepare_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
    target = df["is_fraud"].copy()
    feature_df = df.drop(columns=["is_fraud", "transaction_id", "customer_id"]).copy()

    # Keep imputation simple and explicit for reproducibility.
    for col in feature_df.columns:
        if pd.api.types.is_numeric_dtype(feature_df[col]):
            feature_df[col] = feature_df[col].fillna(feature_df[col].median())
        else:
            feature_df[col] = feature_df[col].fillna("unknown")

    encoded = pd.get_dummies(feature_df, drop_first=False)
    return encoded, target


def perform_feature_selection(
    X: pd.DataFrame,
    y: pd.Series,
    top_k: int,
    seed: int,
    output_dir: Path,
) -> List[str]:
    output_dir.mkdir(parents=True, exist_ok=True)

    selector = VarianceThreshold(threshold=0.001)
    X_var = selector.fit_transform(X)
    X_var_df = pd.DataFrame(X_var, columns=X.columns[selector.get_support()])

    mi = mutual_info_classif(X_var_df, y, random_state=seed)
    mi_series = pd.Series(mi, index=X_var_df.columns, name="mutual_info")

    rf = RandomForestClassifier(
        n_estimators=250,
        random_state=seed,
        max_depth=12,
        min_samples_leaf=2,
        n_jobs=-1,
        class_weight="balanced_subsample",
    )
    rf.fit(X_var_df, y)
    rf_series = pd.Series(rf.feature_importances_, index=X_var_df.columns, name="rf_importance")

    ranked = pd.concat([mi_series, rf_series], axis=1)
    ranked["mi_rank"] = ranked["mutual_info"].rank(ascending=False, method="min")
    ranked["rf_rank"] = ranked["rf_importance"].rank(ascending=False, method="min")
    ranked["combined_rank"] = ranked[["mi_rank", "rf_rank"]].mean(axis=1)
    ranked = ranked.sort_values("combined_rank")

    selected = ranked.head(top_k).index.tolist()
    ranked.to_csv(output_dir / "feature_ranking.csv")

    selected_df = X_var_df[selected].copy()
    selected_df["is_fraud"] = y.values
    selected_df.to_csv(output_dir / "selected_feature_dataset.csv", index=False)

    plt.figure(figsize=(10, 6))
    ranked.head(min(20, len(ranked)))["combined_rank"].sort_values(ascending=False).plot(kind="barh")
    plt.title("Top Features by Combined Rank")
    plt.xlabel("Combined Rank (lower is better)")
    plt.tight_layout()
    plt.savefig(output_dir / "top_features.png", dpi=140)
    plt.close()

    return selected


def quick_model_validation(X: pd.DataFrame, y: pd.Series, selected_features: List[str], seed: int) -> Dict[str, float]:
    X_sel = X[selected_features]

    X_train, X_test, y_train, y_test = train_test_split(
        X_sel,
        y,
        test_size=0.25,
        random_state=seed,
        stratify=y,
    )

    model = RandomForestClassifier(
        n_estimators=280,
        random_state=seed,
        max_depth=14,
        min_samples_leaf=2,
        n_jobs=-1,
        class_weight="balanced_subsample",
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    auc = roc_auc_score(y_test, y_prob)
    report = classification_report(y_test, y_pred, output_dict=True)

    return {
        "roc_auc": float(auc),
        "precision_fraud": float(report["1"]["precision"]),
        "recall_fraud": float(report["1"]["recall"]),
        "f1_fraud": float(report["1"]["f1-score"]),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Synthetic fraud data + EDA + feature selection")
    parser.add_argument("--rows", type=int, default=20_000, help="Number of synthetic rows")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--top-k", type=int, default=20, help="Number of selected features")
    parser.add_argument(
        "--output-root",
        type=str,
        default="ml_models/artifacts",
        help="Output root directory",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_root = Path(args.output_root)

    data_dir = output_root / "data"
    eda_dir = output_root / "eda"
    fs_dir = output_root / "feature_selection"
    data_dir.mkdir(parents=True, exist_ok=True)

    df = generate_synthetic_fraud_dataset(rows=args.rows, seed=args.seed)
    raw_path = data_dir / "synthetic_fraud_transactions.csv"
    df.to_csv(raw_path, index=False)

    eda_summary = run_eda(df, eda_dir)
    X, y = prepare_features(df)
    selected = perform_feature_selection(X, y, top_k=args.top_k, seed=args.seed, output_dir=fs_dir)
    validation = quick_model_validation(X, y, selected_features=selected, seed=args.seed)

    with (output_root / "pipeline_report.md").open("w", encoding="utf-8") as f:
        f.write("# Synthetic Fraud Pipeline Report\n\n")
        f.write(f"- Dataset path: {raw_path}\n")
        f.write(f"- Rows generated: {eda_summary['rows']}\n")
        f.write(f"- Fraud rate: {eda_summary['fraud_rate']:.4f}\n")
        f.write(f"- Selected features ({len(selected)}): {', '.join(selected)}\n")
        f.write(f"- Validation ROC-AUC: {validation['roc_auc']:.4f}\n")
        f.write(f"- Fraud precision: {validation['precision_fraud']:.4f}\n")
        f.write(f"- Fraud recall: {validation['recall_fraud']:.4f}\n")
        f.write(f"- Fraud F1: {validation['f1_fraud']:.4f}\n")

    print("Pipeline complete.")
    print(f"Dataset: {raw_path}")
    print(f"EDA report: {eda_dir / 'eda_summary.md'}")
    print(f"Feature ranking: {fs_dir / 'feature_ranking.csv'}")
    print(f"Pipeline summary: {output_root / 'pipeline_report.md'}")


if __name__ == "__main__":
    main()
