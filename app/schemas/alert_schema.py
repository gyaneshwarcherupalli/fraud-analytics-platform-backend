"""Validation and serialization schemas for alert APIs."""
from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field

class AlertCreate(BaseModel):
    transaction_id: UUID
    fraud_score_id: Optional[UUID] = None
    alert_type: str = Field(..., min_length=1, max_length=60)
    severity: str = Field(..., pattern="^(low|medium|high|critical)$")
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    assigned_to: Optional[str] = Field(None, max_length=120)

class AlertUpdate(BaseModel):
    status: Optional[str] = Field(None, pattern="^(open|acknowledged|in_progress|resolved|closed|dismissed)$")
    severity: Optional[str] = Field(None, pattern="^(low|medium|high|critical)$")
    assigned_to: Optional[str] = Field(None, max_length=120)
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None

class AlertResponse(BaseModel):
    id: UUID
    transaction_id: UUID
    fraud_score_id: Optional[UUID]
    alert_type: str
    severity: str
    status: str
    title: str
    description: Optional[str]
    assigned_to: Optional[str]
    acknowledged_at: Optional[datetime]
    resolved_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}

class AlertListResponse(BaseModel):
    items: List[AlertResponse]
    total: int
    page: int
    page_size: int
    pages: int

class AlertSummaryResponse(BaseModel):
    total_alerts: int
    open_alerts: int
    acknowledged_alerts: int
    resolved_alerts: int
    high_priority_alerts: int
    unassigned_alerts: int
