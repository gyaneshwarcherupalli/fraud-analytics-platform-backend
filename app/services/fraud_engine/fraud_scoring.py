"""Fraud scoring engine built around a trained Random Forest model.

The engine consumes transformed/enriched transaction payloads and returns a
uniform scoring response used by downstream alerting and persistence layers.
"""

from __future__ import annotations

import json
import logging
import pickle
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from app.services.etl.feature_engineering import FeatureEngineeringService
from app.utils.constants import (
	FRAUD_SCORE_THRESHOLD_HIGH,
	FRAUD_SCORE_THRESHOLD_LOW,
	FRAUD_SCORE_THRESHOLD_MEDIUM,
	RISK_LEVEL_CRITICAL,
	RISK_LEVEL_HIGH,
	RISK_LEVEL_LOW,
	RISK_LEVEL_MEDIUM,
)
from app.utils.exceptions import FraudAnalyticsException

logger = logging.getLogger(__name__)


class FraudScoringEngine:
	"""Loads model artifacts and generates fraud scores for transactions."""

	def __init__(
		self,
		artifact_dir: str = "ml_models/artifacts",
		model_file: str = "random_forest.pkl",
		metadata_file: str = "random_forest_metrics.json",
		imputer_file: str = "rf_imputer.pkl",
		scaler_file: str = "rf_scaler.pkl",
	) -> None:
		self.artifact_dir = Path(artifact_dir)
		self.model_path = self.artifact_dir / model_file
		self.metadata_path = self.artifact_dir / metadata_file
		self.imputer_path = self.artifact_dir / imputer_file
		self.scaler_path = self.artifact_dir / scaler_file

		self.model: Any = None
		self.metadata: Dict[str, Any] = {}
		self.imputer: Any = None
		self.scaler: Any = None

		self.feature_service = FeatureEngineeringService()
		self.feature_names: List[str] = []
		self.model_version: str = "rf_v1"
		self.threshold: float = FRAUD_SCORE_THRESHOLD_MEDIUM

	def load(self) -> None:
		"""Load model and preprocessing artifacts from disk."""
		if not self.model_path.exists():
			raise FraudAnalyticsException(
				f"Fraud model artifact not found: {self.model_path}",
				code="MODEL_NOT_FOUND",
			)

		with self.model_path.open("rb") as f:
			self.model = pickle.load(f)

		if self.metadata_path.exists():
			with self.metadata_path.open("r", encoding="utf-8") as f:
				self.metadata = json.load(f)
		else:
			self.metadata = {}

		if self.imputer_path.exists():
			with self.imputer_path.open("rb") as f:
				self.imputer = pickle.load(f)

		if self.scaler_path.exists():
			with self.scaler_path.open("rb") as f:
				self.scaler = pickle.load(f)

		self.feature_names = list(self.metadata.get("feature_names") or [])
		if not self.feature_names and hasattr(self.model, "feature_names_in_"):
			self.feature_names = [str(x) for x in self.model.feature_names_in_]

		self.model_version = str(self.metadata.get("model_version") or "rf_v1")
		self.threshold = float(self.metadata.get("threshold", FRAUD_SCORE_THRESHOLD_MEDIUM))

	def score_transaction(
		self,
		payload: Dict[str, Any],
		*,
		payload_is_enriched: bool = False,
	) -> Dict[str, Any]:
		"""Score a single transaction payload and return model output."""
		self._ensure_loaded()

		enriched_payload = payload if payload_is_enriched else self._build_minimal_enriched_payload(payload)
		features = self.feature_service.build_features(enriched_payload)

		x = self._prepare_model_matrix(features)
		score = self._predict_probability(x)
		risk_level = self._risk_level(score)
		is_fraud = score >= self.threshold
		reason_codes = self._reason_codes(features, score)

		return {
			"transaction_ref": features.get("transaction_ref") or payload.get("transaction_ref"),
			"customer_id": features.get("customer_id") or payload.get("customer_id"),
			"score": round(float(score), 6),
			"model_version": self.model_version,
			"risk_level": risk_level,
			"is_fraud_predicted": bool(is_fraud),
			"threshold": round(float(self.threshold), 6),
			"reason_codes": reason_codes,
			"generated_at": datetime.now(timezone.utc).isoformat(),
		}

	def score_batch(
		self,
		payloads: List[Dict[str, Any]],
		*,
		payload_is_enriched: bool = False,
		skip_errors: bool = True,
	) -> Dict[str, Any]:
		"""Score multiple transactions and optionally continue on per-item errors."""
		scored: List[Dict[str, Any]] = []
		errors: List[Dict[str, Any]] = []

		for idx, payload in enumerate(payloads):
			try:
				scored.append(
					self.score_transaction(
						payload,
						payload_is_enriched=payload_is_enriched,
					)
				)
			except Exception as exc:  # noqa: BLE001
				if not skip_errors:
					raise
				logger.warning("Fraud scoring failed for index %d: %s", idx, exc)
				errors.append({"index": idx, "error": str(exc)})

		return {
			"results": scored,
			"errors": errors,
			"summary": {
				"total": len(payloads),
				"scored": len(scored),
				"failed": len(errors),
			},
		}

	def _ensure_loaded(self) -> None:
		if self.model is None:
			self.load()

	@staticmethod
	def _build_minimal_enriched_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
		merged = dict(payload)
		merged.setdefault("enrichment", {})
		return merged

	def _prepare_model_matrix(self, features: Dict[str, Any]) -> np.ndarray:
		# Remove non-model identifiers.
		numeric_feature_map = {
			k: v for k, v in features.items() if k not in {"transaction_ref", "customer_id"}
		}

		row = pd.DataFrame([numeric_feature_map])
		if self.feature_names:
			for name in self.feature_names:
				if name not in row.columns:
					row[name] = 0.0
			row = row[self.feature_names]

		row = row.apply(pd.to_numeric, errors="coerce")

		x: Any = row
		if self.imputer is not None:
			x = self.imputer.transform(x)
		if self.scaler is not None:
			x = self.scaler.transform(x)
		return x

	def _predict_probability(self, x: np.ndarray) -> float:
		if hasattr(self.model, "predict_proba"):
			prob = float(self.model.predict_proba(x)[0, 1])
			return min(max(prob, 0.0), 1.0)

		if hasattr(self.model, "decision_function"):
			margin = float(self.model.decision_function(x)[0])
			prob = 1.0 / (1.0 + np.exp(-margin))
			return min(max(prob, 0.0), 1.0)

		raise FraudAnalyticsException(
			"Loaded fraud model has no supported inference method",
			code="MODEL_INFERENCE_ERROR",
		)

	@staticmethod
	def _risk_level(score: float) -> str:
		if score >= FRAUD_SCORE_THRESHOLD_HIGH:
			return RISK_LEVEL_CRITICAL
		if score >= FRAUD_SCORE_THRESHOLD_MEDIUM:
			return RISK_LEVEL_HIGH
		if score >= FRAUD_SCORE_THRESHOLD_LOW:
			return RISK_LEVEL_MEDIUM
		return RISK_LEVEL_LOW

	@staticmethod
	def _reason_codes(features: Dict[str, Any], score: float) -> List[str]:
		reasons: List[str] = []

		if int(features.get("velocity_spike_1h", 0)) == 1:
			reasons.append("VELOCITY_SPIKE_1H")
		if int(features.get("velocity_spike_24h", 0)) == 1:
			reasons.append("VELOCITY_SPIKE_24H")
		if int(features.get("merchant_is_high_risk_category", 0)) == 1:
			reasons.append("HIGH_RISK_MERCHANT_CATEGORY")
		if int(features.get("channel_is_high_risk", 0)) == 1:
			reasons.append("HIGH_RISK_CHANNEL")
		if int(features.get("channel_is_card_not_present", 0)) == 1:
			reasons.append("CARD_NOT_PRESENT")
		if int(features.get("location_is_high_risk_country", 0)) == 1:
			reasons.append("HIGH_RISK_COUNTRY")
		if int(features.get("ip_is_valid", 1)) == 0:
			reasons.append("INVALID_IP")
		if float(features.get("customer_risk_score", 0.0)) >= 0.75:
			reasons.append("CUSTOMER_HIGH_RISK_PROFILE")
		if int(features.get("amount_bucket_very_large", 0)) == 1:
			reasons.append("VERY_LARGE_AMOUNT")

		if score >= 0.9:
			reasons.append("EXTREME_MODEL_SCORE")
		elif score >= 0.75:
			reasons.append("ELEVATED_MODEL_SCORE")

		return reasons[:6]
