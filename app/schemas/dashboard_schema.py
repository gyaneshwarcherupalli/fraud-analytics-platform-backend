"""Response contracts for dashboard APIs."""
from datetime import date
from typing import List
from pydantic import BaseModel

class DashboardMetrics(BaseModel):
    transactions_processed: int
    fraud_detected: int
    alerts_generated: int
    open_alerts: int
    average_risk_score: float
    fraud_rate: float

class NamedCount(BaseModel):
    name: str
    count: int

class DailyTrend(BaseModel):
    date: date
    transactions: int
    fraud_detected: int
    alerts: int

class DashboardOverview(BaseModel):
    metrics: DashboardMetrics
    alerts_by_severity: List[NamedCount]
    alerts_by_status: List[NamedCount]
    daily_trend: List[DailyTrend]
