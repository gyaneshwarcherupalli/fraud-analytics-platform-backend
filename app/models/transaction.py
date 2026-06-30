"""SQLAlchemy model for financial transactions."""
import uuid

from sqlalchemy import Column, DateTime, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class Transaction(Base):
	"""Represents a payment transaction ingested by the platform."""

	__tablename__ = "transactions"

	id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
	transaction_ref = Column(String(120), nullable=False, unique=True, index=True)
	customer_id = Column(String(100), nullable=False, index=True)
	amount = Column(Numeric(18, 2), nullable=False)
	currency = Column(String(3), nullable=False)
	merchant_name = Column(String(200), nullable=False)
	merchant_category = Column(String(120), nullable=True)
	transaction_type = Column(String(60), nullable=False)
	channel = Column(String(60), nullable=False)
	device_id = Column(String(120), nullable=True)
	ip_address = Column(String(45), nullable=True)
	location = Column(JSONB, nullable=False, default=dict)
	status = Column(String(30), nullable=False, default="received")
	transaction_metadata = Column(JSONB, nullable=False, default=dict)
	occurred_at = Column(DateTime(timezone=True), nullable=False)
	created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
	updated_at = Column(
		DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
	)

	fraud_scores = relationship("FraudScore", back_populates="transaction", cascade="all, delete-orphan")
	alerts = relationship("Alert", back_populates="transaction", cascade="all, delete-orphan")
