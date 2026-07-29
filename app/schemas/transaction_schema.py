"""Pydantic schemas for transaction request/response serialization."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class TransactionCreate(BaseModel):
    """Payload for creating a new transaction via the REST API."""

    transaction_ref: Optional[str] = Field(None, max_length=120, description="Unique transaction reference; auto-generated if omitted")
    customer_id: str = Field(..., min_length=1, max_length=100)
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    currency: str = Field(..., min_length=3, max_length=3)
    merchant_name: str = Field(..., min_length=1, max_length=200)
    merchant_category: Optional[str] = Field(None, max_length=120)
    transaction_type: str = Field(default="purchase", max_length=60)
    channel: str = Field(default="web", max_length=60)
    device_id: Optional[str] = Field(None, max_length=120)
    ip_address: Optional[str] = Field(None, max_length=45)
    location: Dict[str, Any] = Field(default_factory=dict)
    transaction_metadata: Dict[str, Any] = Field(default_factory=dict)
    occurred_at: Optional[datetime] = None

    @field_validator("currency")
    @classmethod
    def currency_upper(cls, v: str) -> str:
        return v.upper()


class TransactionStatusUpdate(BaseModel):
    """Payload for updating a transaction's processing status."""

    status: str = Field(..., pattern="^(received|pending|approved|rejected|review)$")


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class TransactionResponse(BaseModel):
    """Full transaction representation returned by the API."""

    id: UUID
    transaction_ref: str
    customer_id: str
    amount: Decimal
    currency: str
    merchant_name: str
    merchant_category: Optional[str]
    transaction_type: str
    channel: str
    device_id: Optional[str]
    ip_address: Optional[str]
    location: Dict[str, Any]
    status: str
    transaction_metadata: Dict[str, Any]
    occurred_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TransactionListResponse(BaseModel):
    """Paginated list of transactions."""

    items: List[TransactionResponse]
    total: int
    page: int
    page_size: int
    pages: int
