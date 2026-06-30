"""SQLAlchemy model for customer risk profile data."""
import uuid

from sqlalchemy import Column, DateTime, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.database import Base


class CustomerRisk(Base):
	"""Stores risk profile and factors for a customer."""

	__tablename__ = "customer_risks"

	id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
	customer_id = Column(String(100), nullable=False, unique=True, index=True)
	risk_score = Column(Numeric(5, 2), nullable=False)
	risk_level = Column(String(20), nullable=False)
	risk_factors = Column(JSONB, nullable=False, default=dict)
	last_evaluated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
	created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
	updated_at = Column(
		DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
	)
