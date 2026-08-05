"""Alert workflow business logic."""
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session
from app.repositories.alert_repository import AlertRepository
from app.schemas.alert_schema import AlertCreate, AlertUpdate

class AlertService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = AlertRepository(db)

    def create(self, payload: AlertCreate):
        alert = self.repository.create(payload)
        self.db.commit()
        self.db.refresh(alert)
        return alert

    def update(self, alert_id: UUID, payload: AlertUpdate):
        alert = self.repository.get_by_id(alert_id)
        if alert is None: return None
        alert = self.repository.update(alert, payload)
        self.db.commit()
        self.db.refresh(alert)
        return alert

    def list(self, *, page: int, page_size: int, status: Optional[str] = None,
             severity: Optional[str] = None, assigned_to: Optional[str] = None,
             transaction_id: Optional[UUID] = None):
        return self.repository.list_alerts(page=page, page_size=page_size, status=status,
            severity=severity, assigned_to=assigned_to, transaction_id=transaction_id)
