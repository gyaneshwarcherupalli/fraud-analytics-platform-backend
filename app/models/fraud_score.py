"""SQLAlchemy model for fraud scoring results."""
import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class FraudScore(Base):
	"""Stores model output generated for a transaction."""

	__tablename__ = "fraud_scores"

	id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
	transaction_id = Column(UUID(as_uuid=True), ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False, index=True)
	score = Column(Numeric(6, 4), nullable=False, index=True)
	model_version = Column(String(50), nullable=False)
	risk_level = Column(String(20), nullable=False)
	is_fraud_predicted = Column(Boolean, nullable=False, default=False)
	reason_codes = Column(JSONB, nullable=False, default=list)
	generated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
	created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

	transaction = relationship("Transaction", back_populates="fraud_scores")
	alerts = relationship("Alert", back_populates="fraud_score")
