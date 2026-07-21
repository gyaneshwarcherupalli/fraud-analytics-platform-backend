"""Train an Isolation Forest model and persist model artifacts.

Usage:
	python ml_models/training/train_isolation_forest.py
"""

from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.preprocessing import StandardScaler


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Train Isolation Forest for fraud anomaly detection")
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
	parser.add_argument("--n-estimators", type=int, default=300, help="Number of trees")
	parser.add_argument(
		"--contamination",
		type=float,
		default=None,
		help="Expected anomaly ratio; if omitted, estimated from labeled fraud rate",
	)
	return parser.parse_args()


def load_dataset(path: Path) -> Tuple[pd.DataFrame, pd.Series]:
	if not path.exists():
		raise FileNotFoundError(f"Training data not found: {path}")

	df = pd.read_csv(path)
	if "is_fraud" not in df.columns:
		raise ValueError("Dataset must contain 'is_fraud' column for evaluation and contamination estimate")

	y = df["is_fraud"].astype(int)
	X = df.drop(columns=["is_fraud"]).copy()
	return X, y


def preprocess_features(X: pd.DataFrame) -> Tuple[np.ndarray, SimpleImputer, StandardScaler, list[str]]:
	X_num = X.select_dtypes(include=["number"]).copy()
	feature_names = X_num.columns.tolist()

	imputer = SimpleImputer(strategy="median")
	X_imputed = imputer.fit_transform(X_num)

	scaler = StandardScaler()
	X_scaled = scaler.fit_transform(X_imputed)

	return X_scaled, imputer, scaler, feature_names


def train_and_evaluate(
	X_scaled: np.ndarray,
	y: pd.Series,
	seed: int,
	n_estimators: int,
	contamination: float,
) -> Tuple[IsolationForest, Dict[str, float], np.ndarray]:
	model = IsolationForest(
		n_estimators=n_estimators,
		contamination=contamination,
		random_state=seed,
		n_jobs=-1,
	)
	model.fit(X_scaled)

	raw_predictions = model.predict(X_scaled)
	y_pred = (raw_predictions == -1).astype(int)

	# Negating the decision function makes higher scores indicate higher anomaly risk.
	anomaly_score = -model.decision_function(X_scaled)

	metrics: Dict[str, float] = {
		"accuracy": float(accuracy_score(y, y_pred)),
		"precision": float(precision_score(y, y_pred, zero_division=0)),
		"recall": float(recall_score(y, y_pred, zero_division=0)),
		"f1_score": float(f1_score(y, y_pred, zero_division=0)),
		"roc_auc": float(roc_auc_score(y, anomaly_score)),
		"samples": float(len(y)),
		"predicted_anomaly_rate": float(y_pred.mean()),
	}
	return model, metrics, anomaly_score


def save_artifacts(
	output_dir: Path,
	model: IsolationForest,
	imputer: SimpleImputer,
	scaler: StandardScaler,
	feature_names: list[str],
	metrics: Dict[str, float],
	contamination: float,
) -> None:
	output_dir.mkdir(parents=True, exist_ok=True)

	with (output_dir / "isolation_forest.pkl").open("wb") as f:
		pickle.dump(model, f)

	with (output_dir / "scaler.pkl").open("wb") as f:
		pickle.dump(scaler, f)

	with (output_dir / "imputer.pkl").open("wb") as f:
		pickle.dump(imputer, f)

	metadata = {
		"feature_names": feature_names,
		"contamination": contamination,
		"metrics": metrics,
	}

	with (output_dir / "isolation_forest_metrics.json").open("w", encoding="utf-8") as f:
		json.dump(metadata, f, indent=2)

	with (output_dir / "isolation_forest_training_report.md").open("w", encoding="utf-8") as f:
		f.write("# Isolation Forest Training Report\n\n")
		f.write(f"- Model: IsolationForest\n")
		f.write(f"- Features used: {len(feature_names)}\n")
		f.write(f"- Contamination: {contamination:.6f}\n")
		for key, value in metrics.items():
			if key == "samples":
				f.write(f"- {key}: {int(value)}\n")
			else:
				f.write(f"- {key}: {value:.6f}\n")


def main() -> None:
	args = parse_args()
	input_path = Path(args.input)
	output_dir = Path(args.output_dir)

	X, y = load_dataset(input_path)
	X_scaled, imputer, scaler, feature_names = preprocess_features(X)

	if args.contamination is not None:
		contamination = float(args.contamination)
	else:
		estimated = float(y.mean())
		contamination = min(max(estimated, 0.005), 0.20)

	model, metrics, _ = train_and_evaluate(
		X_scaled=X_scaled,
		y=y,
		seed=args.seed,
		n_estimators=args.n_estimators,
		contamination=contamination,
	)

	save_artifacts(
		output_dir=output_dir,
		model=model,
		imputer=imputer,
		scaler=scaler,
		feature_names=feature_names,
		metrics=metrics,
		contamination=contamination,
	)

	print("Isolation Forest training complete.")
	print(f"Training data: {input_path}")
	print(f"Artifacts directory: {output_dir}")
	print(f"Saved model: {output_dir / 'isolation_forest.pkl'}")
	print(f"Saved scaler: {output_dir / 'scaler.pkl'}")
	print(f"Saved imputer: {output_dir / 'imputer.pkl'}")
	print(f"Saved metrics: {output_dir / 'isolation_forest_metrics.json'}")
	print(f"Saved report: {output_dir / 'isolation_forest_training_report.md'}")


if __name__ == "__main__":
	main()
