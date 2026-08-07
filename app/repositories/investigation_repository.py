"""Database operations for alert investigations."""
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.investigation import Investigation
from app.schemas.investigation_schema import InvestigationCreate, InvestigationUpdate
from app.utils.exceptions import DataNotFoundError


class InvestigationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, payload: InvestigationCreate) -> Investigation:
        alert_exists = self.db.scalar(select(Alert.id).where(Alert.id == payload.alert_id))
        if alert_exists is None:
            raise DataNotFoundError("Alert not found")
        investigation = Investigation(**payload.model_dump(), status="pending", findings={})
        self.db.add(investigation)
        self.db.flush()
        return investigation

    def get_by_id(self, investigation_id: UUID) -> Optional[Investigation]:
        return self.db.execute(select(Investigation).where(
            Investigation.id == investigation_id)).scalar_one_or_none()

    def list_investigations(
        self, *, page: int, page_size: int, status: Optional[str] = None,
        priority: Optional[str] = None, investigator: Optional[str] = None,
        alert_id: Optional[UUID] = None,
    ) -> Tuple[List[Investigation], int]:
        stmt = select(Investigation)
        if status:
            stmt = stmt.where(Investigation.status == status)
        if priority:
            stmt = stmt.where(Investigation.priority == priority)
        if investigator:
            stmt = stmt.where(Investigation.investigator == investigator)
        if alert_id:
            stmt = stmt.where(Investigation.alert_id == alert_id)
        total = int(self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
        items = list(self.db.execute(stmt.order_by(
            Investigation.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        ).scalars().all())
        return items, total

    def update(self, investigation: Investigation, payload: InvestigationUpdate) -> Investigation:
        changes = payload.model_dump(exclude_unset=True)
        now = datetime.now(timezone.utc)
        next_status = changes.get("status")
        if next_status == "in_progress" and investigation.started_at is None:
            investigation.started_at = now
        if next_status in {"completed", "closed"} and investigation.closed_at is None:
            investigation.closed_at = now
        for field, value in changes.items():
            setattr(investigation, field, value)
        self.db.flush()
        return investigation

    def queue_summary(self) -> Dict[str, int]:
        today = datetime.now(timezone.utc).date()
        rows = self.db.execute(select(
            Investigation.status, Investigation.priority, Investigation.investigator,
            Investigation.closed_at, func.count(Investigation.id),
        ).group_by(
            Investigation.status, Investigation.priority, Investigation.investigator,
            Investigation.closed_at,
        )).all()
        result = {"total": 0, "pending": 0, "in_progress": 0, "completed_today": 0,
                  "unassigned": 0, "high_priority": 0}
        for status, priority, investigator, closed_at, count in rows:
            count = int(count)
            result["total"] += count
            if status == "pending":
                result["pending"] += count
            if status == "in_progress":
                result["in_progress"] += count
            if status in {"completed", "closed"} and closed_at and closed_at.date() == today:
                result["completed_today"] += count
            if investigator is None:
                result["unassigned"] += count
            if priority in {"high", "critical"} and status not in {"completed", "closed", "cancelled"}:
                result["high_priority"] += count
        return result
