"""Database access for fraud alerts."""
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models.alert import Alert
from app.schemas.alert_schema import AlertCreate, AlertUpdate

class AlertRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, payload: AlertCreate) -> Alert:
        alert = Alert(**payload.model_dump(), status="open")
        self.db.add(alert)
        self.db.flush()
        return alert

    def get_by_id(self, alert_id: UUID) -> Optional[Alert]:
        return self.db.execute(select(Alert).where(Alert.id == alert_id)).scalar_one_or_none()

    def list_alerts(self, *, page: int, page_size: int, status: Optional[str] = None,
                    severity: Optional[str] = None, assigned_to: Optional[str] = None,
                    transaction_id: Optional[UUID] = None) -> Tuple[List[Alert], int]:
        stmt = select(Alert)
        if status: stmt = stmt.where(Alert.status == status)
        if severity: stmt = stmt.where(Alert.severity == severity)
        if assigned_to: stmt = stmt.where(Alert.assigned_to == assigned_to)
        if transaction_id: stmt = stmt.where(Alert.transaction_id == transaction_id)
        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        items = list(self.db.execute(stmt.order_by(Alert.created_at.desc())
                                    .offset((page - 1) * page_size).limit(page_size)).scalars().all())
        return items, int(total)

    def update(self, alert: Alert, payload: AlertUpdate) -> Alert:
        changes = payload.model_dump(exclude_unset=True)
        now = datetime.now(timezone.utc)
        if changes.get("status") == "acknowledged" and alert.acknowledged_at is None:
            alert.acknowledged_at = now
        if changes.get("status") in {"resolved", "closed"} and alert.resolved_at is None:
            alert.resolved_at = now
        for field, value in changes.items(): setattr(alert, field, value)
        self.db.flush()
        return alert

    def summary(self) -> Dict[str, int]:
        rows = self.db.execute(select(Alert.status, Alert.severity, Alert.assigned_to,
            func.count(Alert.id)).group_by(Alert.status, Alert.severity, Alert.assigned_to)).all()
        result = {"total_alerts": 0, "open_alerts": 0, "acknowledged_alerts": 0,
                  "resolved_alerts": 0, "high_priority_alerts": 0, "unassigned_alerts": 0}
        for status, severity, assigned_to, count in rows:
            count = int(count)
            result["total_alerts"] += count
            if status in {"open", "in_progress"}: result["open_alerts"] += count
            if status == "acknowledged": result["acknowledged_alerts"] += count
            if status in {"resolved", "closed"}: result["resolved_alerts"] += count
            if severity in {"high", "critical"}: result["high_priority_alerts"] += count
            if assigned_to is None: result["unassigned_alerts"] += count
        return result
