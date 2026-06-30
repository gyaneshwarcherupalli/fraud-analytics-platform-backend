"""SQLAlchemy model for alert investigations."""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class Investigation(Base):
	"""Tracks investigation workflows for generated alerts."""

	__tablename__ = "investigations"

	id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
	alert_id = Column(UUID(as_uuid=True), ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False, index=True)
	investigator = Column(String(120), nullable=True)
	status = Column(String(30), nullable=False, default="pending")
	priority = Column(String(20), nullable=False, default="medium")
	notes = Column(Text, nullable=True)
	findings = Column(JSONB, nullable=False, default=dict)
	started_at = Column(DateTime(timezone=True), nullable=True)
	closed_at = Column(DateTime(timezone=True), nullable=True)
	created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
	updated_at = Column(
		DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
	)

	alert = relationship("Alert", back_populates="investigations")
