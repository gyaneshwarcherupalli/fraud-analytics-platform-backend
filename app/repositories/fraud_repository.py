"""Repository helpers for persisting and querying fraud score records."""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.fraud_score import FraudScore


class FraudRepository:
	"""Database operations for the FraudScore model."""

	def __init__(self, db: Session) -> None:
		self.db = db

	# ------------------------------------------------------------------
	# Write helpers
	# ------------------------------------------------------------------

	def create_fraud_score(
		self,
		transaction_id: UUID,
		score_data: Dict[str, Any],
	) -> FraudScore:
		"""Persist a fraud score produced by the scoring engine.

		Args:
			transaction_id: FK to the transactions table.
			score_data: Dict returned by ``FraudScoringEngine.score_transaction``.
		"""
		raw_score = score_data.get("score", 0.0)
		instance = FraudScore(
			transaction_id=transaction_id,
			score=Decimal(str(raw_score)),
			model_version=str(score_data.get("model_version") or "unknown"),
			risk_level=str(score_data.get("risk_level") or "LOW"),
			is_fraud_predicted=bool(score_data.get("is_fraud_predicted", False)),
			reason_codes=list(score_data.get("reason_codes") or []),
		)
		self.db.add(instance)
		return instance

	# ------------------------------------------------------------------
	# Read helpers
	# ------------------------------------------------------------------

	def get_by_id(self, score_id: UUID) -> Optional[FraudScore]:
		"""Return a single fraud score record by primary key, or None."""
		return self.db.execute(
			select(FraudScore).where(FraudScore.id == score_id)
		).scalar_one_or_none()

	def get_latest_for_transaction(self, transaction_id: UUID) -> Optional[FraudScore]:
		"""Return the most recent fraud score for a transaction."""
		return self.db.execute(
			select(FraudScore)
			.where(FraudScore.transaction_id == transaction_id)
			.order_by(FraudScore.generated_at.desc())
			.limit(1)
		).scalar_one_or_none()

	def list_for_transaction(self, transaction_id: UUID) -> List[FraudScore]:
		"""Return all fraud scores for a given transaction, newest first."""
		return list(
			self.db.execute(
				select(FraudScore)
				.where(FraudScore.transaction_id == transaction_id)
				.order_by(FraudScore.generated_at.desc())
			).scalars().all()
		)

	def list_fraud_scores(
		self,
		*,
		page: int = 1,
		page_size: int = 50,
		risk_level: Optional[str] = None,
		is_fraud_predicted: Optional[bool] = None,
	) -> Tuple[List[FraudScore], int]:
		"""Return a page of fraud score records and the total count.

		Returns:
			(items, total)
		"""
		stmt = select(FraudScore)

		if risk_level:
			stmt = stmt.where(FraudScore.risk_level == risk_level.upper())
		if is_fraud_predicted is not None:
			stmt = stmt.where(FraudScore.is_fraud_predicted == is_fraud_predicted)

		total: int = self.db.execute(
			select(func.count()).select_from(stmt.subquery())
		).scalar_one()

		offset = (page - 1) * page_size
		items: List[FraudScore] = list(
			self.db.execute(
				stmt.order_by(FraudScore.generated_at.desc()).offset(offset).limit(page_size)
			).scalars().all()
		)
		return items, total
