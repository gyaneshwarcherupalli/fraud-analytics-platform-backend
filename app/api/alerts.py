"""Alert creation, triage, and reporting endpoints."""
from math import ceil
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.repositories.alert_repository import AlertRepository
from app.schemas.alert_schema import AlertCreate, AlertListResponse, AlertResponse, AlertSummaryResponse, AlertUpdate
from app.services.alerts.alert_service import AlertService

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

@router.get("/summary", response_model=AlertSummaryResponse, summary="Get alert summary")
def get_alert_summary(db: Session = Depends(get_db)) -> AlertSummaryResponse:
    return AlertSummaryResponse(**AlertRepository(db).summary())

@router.post("", response_model=AlertResponse, status_code=201, summary="Create alert")
def create_alert(payload: AlertCreate, db: Session = Depends(get_db)) -> AlertResponse:
    try: return AlertResponse.model_validate(AlertService(db).create(payload))
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Unable to create alert") from exc

@router.get("", response_model=AlertListResponse, summary="List alerts")
def list_alerts(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=500),
                status: Optional[str] = None, severity: Optional[str] = None,
                assigned_to: Optional[str] = None, transaction_id: Optional[UUID] = None,
                db: Session = Depends(get_db)) -> AlertListResponse:
    items, total = AlertService(db).list(page=page, page_size=page_size, status=status,
        severity=severity, assigned_to=assigned_to, transaction_id=transaction_id)
    return AlertListResponse(items=[AlertResponse.model_validate(x) for x in items], total=total,
        page=page, page_size=page_size, pages=ceil(total / page_size))

@router.get("/{alert_id}", response_model=AlertResponse, summary="Get alert")
def get_alert(alert_id: UUID, db: Session = Depends(get_db)) -> AlertResponse:
    alert = AlertRepository(db).get_by_id(alert_id)
    if alert is None: raise HTTPException(status_code=404, detail="Alert not found")
    return AlertResponse.model_validate(alert)

@router.patch("/{alert_id}", response_model=AlertResponse, summary="Update alert")
def update_alert(alert_id: UUID, payload: AlertUpdate, db: Session = Depends(get_db)) -> AlertResponse:
    try: alert = AlertService(db).update(alert_id, payload)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Unable to update alert") from exc
    if alert is None: raise HTTPException(status_code=404, detail="Alert not found")
    return AlertResponse.model_validate(alert)
