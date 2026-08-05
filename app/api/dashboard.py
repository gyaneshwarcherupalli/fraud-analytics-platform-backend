"""Dashboard and KPI endpoints."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.alert import Alert
from app.schemas.dashboard_schema import DashboardMetrics, DashboardOverview, DailyTrend, NamedCount
from app.services.dashboard.dashboard_service import DashboardService

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

@router.get("/metrics", response_model=DashboardMetrics, summary="Get dashboard metrics")
def get_dashboard_metrics(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)) -> DashboardMetrics:
    return DashboardService(db).metrics(days)

@router.get("/trends", response_model=list[DailyTrend], summary="Get daily dashboard trend")
def get_dashboard_trends(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)) -> list[DailyTrend]:
    return DashboardService(db).trend(days)

@router.get("/alerts/severity", response_model=list[NamedCount], summary="Alerts by severity")
def get_alert_severity(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)) -> list[NamedCount]:
    return DashboardService(db).distribution(Alert.severity, days)

@router.get("/overview", response_model=DashboardOverview, summary="Get dashboard overview")
def get_dashboard_overview(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)) -> DashboardOverview:
    return DashboardService(db).overview(days)
