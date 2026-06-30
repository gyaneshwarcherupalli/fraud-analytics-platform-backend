"""SQLAlchemy model for fraud alerts."""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class Alert(Base):
	"""Represents an alert raised by fraud detection workflows."""

	__tablename__ = "alerts"

	id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
	transaction_id = Column(UUID(as_uuid=True), ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False)
	fraud_score_id = Column(UUID(as_uuid=True), ForeignKey("fraud_scores.id", ondelete="SET NULL"), nullable=True)
	alert_type = Column(String(60), nullable=False)
	severity = Column(String(20), nullable=False, index=True)
	status = Column(String(30), nullable=False, default="open", index=True)
	title = Column(String(200), nullable=False)
	description = Column(Text, nullable=True)
	assigned_to = Column(String(120), nullable=True)
	acknowledged_at = Column(DateTime(timezone=True), nullable=True)
	resolved_at = Column(DateTime(timezone=True), nullable=True)
	created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
	updated_at = Column(
		DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
	)

	transaction = relationship("Transaction", back_populates="alerts")
	fraud_score = relationship("FraudScore", back_populates="alerts")
	investigations = relationship("Investigation", back_populates="alert", cascade="all, delete-orphan")
