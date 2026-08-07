"""Request and response schemas for investigation workflows."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class InvestigationCreate(BaseModel):
    alert_id: UUID
    investigator: Optional[str] = Field(None, max_length=120)
    priority: str = Field("medium", pattern="^(low|medium|high|critical)$")
    notes: Optional[str] = None


class InvestigationUpdate(BaseModel):
    investigator: Optional[str] = Field(None, max_length=120)
    status: Optional[str] = Field(None, pattern="^(pending|in_progress|completed|closed|cancelled)$")
    priority: Optional[str] = Field(None, pattern="^(low|medium|high|critical)$")
    notes: Optional[str] = None
    findings: Optional[Dict[str, Any]] = None


class InvestigationResponse(BaseModel):
    id: UUID
    alert_id: UUID
    investigator: Optional[str]
    status: str
    priority: str
    notes: Optional[str]
    findings: Dict[str, Any]
    started_at: Optional[datetime]
    closed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InvestigationListResponse(BaseModel):
    items: List[InvestigationResponse]
    total: int
    page: int
    page_size: int
    pages: int


class InvestigationQueueResponse(BaseModel):
    total: int
    pending: int
    in_progress: int
    completed_today: int
    unassigned: int
    high_priority: int
