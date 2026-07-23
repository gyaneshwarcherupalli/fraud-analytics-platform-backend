"""Train a Random Forest fraud classifier and persist model artifacts.

Usage:
	python ml_models/training/train_random_forest.py
"""

from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
	accuracy_score,
	f1_score,
	precision_recall_curve,
	precision_score,
	recall_score,
	roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Train Random Forest for fraud detection")
	parser.add_argument(
		"--input",
		type=str,
		default="ml_models/artifacts/feature_selection/selected_feature_dataset.csv",
		help="Path to prepared training dataset",
	)
	parser.add_argument(
		"--output-dir",
		type=str,
		default="ml_models/artifacts",
		help="Directory to save model artifacts",
	)
	parser.add_argument("--seed", type=int, default=42, help="Random seed")
	parser.add_argument("--n-estimators", type=int, default=400, help="Number of trees")
	parser.add_argument("--max-depth", type=int, default=14, help="Maximum tree depth")
	parser.add_argument(
		"--test-size", type=float, default=0.25, help="Holdout split size for evaluation"
	)
	return parser.parse_args()


def load_dataset(path: Path) -> Tuple[pd.DataFrame, pd.Series]:
	if not path.exists():
		raise FileNotFoundError(f"Training data not found: {path}")

	df = pd.read_csv(path)
	if "is_fraud" not in df.columns:
		raise ValueError("Dataset must contain 'is_fraud' column")

	y = df["is_fraud"].astype(int)
	X = df.drop(columns=["is_fraud"]).copy()
	return X, y


def preprocess_features(
	X_train: pd.DataFrame,
	X_test: pd.DataFrame,
) -> Tuple[np.ndarray, np.ndarray, SimpleImputer, StandardScaler, List[str]]:
	X_train_num = X_train.select_dtypes(include=["number"]).copy()
	X_test_num = X_test[X_train_num.columns].copy()
	feature_names = X_train_num.columns.tolist()

	imputer = SimpleImputer(strategy="median")
	X_train_imputed = imputer.fit_transform(X_train_num)
	X_test_imputed = imputer.transform(X_test_num)

	scaler = StandardScaler()
	X_train_scaled = scaler.fit_transform(X_train_imputed)
	X_test_scaled = scaler.transform(X_test_imputed)

	return X_train_scaled, X_test_scaled, imputer, scaler, feature_names


def best_threshold_by_f1(y_true: pd.Series, y_prob: np.ndarray) -> Tuple[float, float]:
	precision, recall, thresholds = precision_recall_curve(y_true, y_prob)
	if len(thresholds) == 0:
		return 0.5, 0.0

	f1_values = (2 * precision[:-1] * recall[:-1]) / (precision[:-1] + recall[:-1] + 1e-12)
	idx = int(np.argmax(f1_values))
	return float(thresholds[idx]), float(f1_values[idx])


def train_and_evaluate(
	X_train: np.ndarray,
	X_test: np.ndarray,
	y_train: pd.Series,
	y_test: pd.Series,
	seed: int,
	n_estimators: int,
	max_depth: int,
) -> Tuple[RandomForestClassifier, Dict[str, float], float, np.ndarray]:
	model = RandomForestClassifier(
		n_estimators=n_estimators,
		random_state=seed,
		max_depth=max_depth,
		min_samples_leaf=2,
		n_jobs=-1,
		class_weight="balanced_subsample",
	)
	model.fit(X_train, y_train)

	y_prob = model.predict_proba(X_test)[:, 1]
	threshold, best_f1 = best_threshold_by_f1(y_test, y_prob)
	y_pred = (y_prob >= threshold).astype(int)

	metrics: Dict[str, float] = {
		"accuracy": float(accuracy_score(y_test, y_pred)),
		"precision": float(precision_score(y_test, y_pred, zero_division=0)),
		"recall": float(recall_score(y_test, y_pred, zero_division=0)),
		"f1_score": float(f1_score(y_test, y_pred, zero_division=0)),
		"roc_auc": float(roc_auc_score(y_test, y_prob)),
		"best_f1_from_pr_curve": float(best_f1),
		"predicted_positive_rate": float(y_pred.mean()),
		"samples_train": float(len(y_train)),
		"samples_test": float(len(y_test)),
	}

	return model, metrics, threshold, y_prob


def save_artifacts(
	output_dir: Path,
	model: RandomForestClassifier,
	imputer: SimpleImputer,
	scaler: StandardScaler,
	feature_names: List[str],
	metrics: Dict[str, float],
	threshold: float,
) -> None:
	output_dir.mkdir(parents=True, exist_ok=True)

	with (output_dir / "random_forest.pkl").open("wb") as f:
		pickle.dump(model, f)

	with (output_dir / "rf_imputer.pkl").open("wb") as f:
		pickle.dump(imputer, f)

	with (output_dir / "rf_scaler.pkl").open("wb") as f:
		pickle.dump(scaler, f)

	importance_pairs = sorted(
		zip(feature_names, model.feature_importances_),
		key=lambda x: x[1],
		reverse=True,
	)

	metadata = {
		"model_name": "RandomForestClassifier",
		"model_version": "rf_v1",
		"feature_names": feature_names,
		"threshold": threshold,
		"metrics": metrics,
		"top_feature_importances": [
			{"feature": feat, "importance": float(imp)}
			for feat, imp in importance_pairs[:20]
		],
	}

	with (output_dir / "random_forest_metrics.json").open("w", encoding="utf-8") as f:
		json.dump(metadata, f, indent=2)

	with (output_dir / "random_forest_training_report.md").open("w", encoding="utf-8") as f:
		f.write("# Random Forest Training Report\n\n")
		f.write("- Model: RandomForestClassifier\n")
		f.write(f"- Features used: {len(feature_names)}\n")
		f.write(f"- Inference threshold: {threshold:.6f}\n")
		for key, value in metrics.items():
			if key.startswith("samples"):
				f.write(f"- {key}: {int(value)}\n")
			else:
				f.write(f"- {key}: {value:.6f}\n")


def main() -> None:
	args = parse_args()
	input_path = Path(args.input)
	output_dir = Path(args.output_dir)

	X, y = load_dataset(input_path)
	X_train, X_test, y_train, y_test = train_test_split(
		X,
		y,
		test_size=args.test_size,
		random_state=args.seed,
		stratify=y,
	)

	X_train_proc, X_test_proc, imputer, scaler, feature_names = preprocess_features(
		X_train,
		X_test,
	)

	model, metrics, threshold, _ = train_and_evaluate(
		X_train=X_train_proc,
		X_test=X_test_proc,
		y_train=y_train,
		y_test=y_test,
		seed=args.seed,
		n_estimators=args.n_estimators,
		max_depth=args.max_depth,
	)

	save_artifacts(
		output_dir=output_dir,
		model=model,
		imputer=imputer,
		scaler=scaler,
		feature_names=feature_names,
		metrics=metrics,
		threshold=threshold,
	)

	print("Random Forest training complete.")
	print(f"Training data: {input_path}")
	print(f"Artifacts directory: {output_dir}")
	print(f"Saved model: {output_dir / 'random_forest.pkl'}")
	print(f"Saved imputer: {output_dir / 'rf_imputer.pkl'}")
	print(f"Saved scaler: {output_dir / 'rf_scaler.pkl'}")
	print(f"Saved metrics: {output_dir / 'random_forest_metrics.json'}")
	print(f"Saved report: {output_dir / 'random_forest_training_report.md'}")


if __name__ == "__main__":
	main()
