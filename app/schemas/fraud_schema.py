"""Pydantic schemas for fraud scoring request/response serialization."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class FraudScoreRequest(BaseModel):
    """Payload for scoring a single transaction."""

    transaction_ref: Optional[str] = Field(None, description="Existing transaction reference to score")
    # Raw transaction fields (used when scoring an ad-hoc payload)
    customer_id: Optional[str] = None
    amount: Optional[float] = Field(None, gt=0)
    currency: Optional[str] = Field(None, min_length=3, max_length=3)
    merchant_name: Optional[str] = None
    merchant_category: Optional[str] = None
    transaction_type: Optional[str] = None
    channel: Optional[str] = None
    device_id: Optional[str] = None
    ip_address: Optional[str] = None
    location: Dict[str, Any] = Field(default_factory=dict)
    transaction_metadata: Dict[str, Any] = Field(default_factory=dict)


class FraudScoreBatchRequest(BaseModel):
    """Payload for scoring multiple transactions in one call."""

    transactions: List[FraudScoreRequest] = Field(..., min_length=1, max_length=500)
    skip_errors: bool = Field(default=True, description="Continue scoring on per-item errors")


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class FraudScoreResult(BaseModel):
    """Single fraud score result."""

    transaction_ref: Optional[str]
    customer_id: Optional[str]
    score: float = Field(ge=0, le=1)
    model_version: str
    risk_level: str
    is_fraud_predicted: bool
    threshold: float
    reason_codes: List[str]
    generated_at: str


class FraudScoreBatchResponse(BaseModel):
    """Response for batch scoring endpoint."""

    results: List[FraudScoreResult]
    errors: List[Dict[str, Any]]
    summary: Dict[str, int]


class FraudScoreRecord(BaseModel):
    """Persisted fraud score record returned from the database."""

    id: UUID
    transaction_id: UUID
    score: float
    model_version: str
    risk_level: str
    is_fraud_predicted: bool
    reason_codes: List[str]
    generated_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class FraudScoreListResponse(BaseModel):
    """Paginated list of fraud score records."""

    items: List[FraudScoreRecord]
    total: int
    page: int
    page_size: int
    pages: int
