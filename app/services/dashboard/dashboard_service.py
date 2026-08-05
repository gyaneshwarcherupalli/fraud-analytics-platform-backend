"""Aggregations used by dashboard endpoints."""
from datetime import date, datetime, time, timedelta, timezone
from typing import Dict, List
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models.alert import Alert
from app.models.fraud_score import FraudScore
from app.models.transaction import Transaction
from app.schemas.dashboard_schema import DashboardMetrics, DashboardOverview, DailyTrend, NamedCount

class DashboardService:
    def __init__(self, db: Session) -> None: self.db = db

    def metrics(self, days: int = 30) -> DashboardMetrics:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        transactions = int(self.db.scalar(select(func.count(Transaction.id)).where(Transaction.occurred_at >= since)) or 0)
        fraud = int(self.db.scalar(select(func.count(FraudScore.id)).where(
            FraudScore.generated_at >= since, FraudScore.is_fraud_predicted.is_(True))) or 0)
        alerts = int(self.db.scalar(select(func.count(Alert.id)).where(Alert.created_at >= since)) or 0)
        open_alerts = int(self.db.scalar(select(func.count(Alert.id)).where(
            Alert.created_at >= since, Alert.status.in_(["open", "acknowledged", "in_progress"]))) or 0)
        average = self.db.scalar(select(func.avg(FraudScore.score)).where(FraudScore.generated_at >= since))
        return DashboardMetrics(transactions_processed=transactions, fraud_detected=fraud,
            alerts_generated=alerts, open_alerts=open_alerts, average_risk_score=round(float(average or 0), 4),
            fraud_rate=round((fraud / transactions * 100) if transactions else 0, 2))

    def distribution(self, column, days: int) -> List[NamedCount]:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        rows = self.db.execute(select(column, func.count(Alert.id)).where(
            Alert.created_at >= since).group_by(column).order_by(func.count(Alert.id).desc())).all()
        return [NamedCount(name=str(name), count=int(count)) for name, count in rows]

    def trend(self, days: int = 30) -> List[DailyTrend]:
        first_day = date.today() - timedelta(days=days - 1)
        since = datetime.combine(first_day, time.min, tzinfo=timezone.utc)
        buckets: Dict[date, Dict[str, int]] = {first_day + timedelta(days=i):
            {"transactions": 0, "fraud_detected": 0, "alerts": 0} for i in range(days)}
        for occurred_at in self.db.scalars(select(Transaction.occurred_at).where(Transaction.occurred_at >= since)):
            buckets[occurred_at.date()]["transactions"] += 1
        for generated_at in self.db.scalars(select(FraudScore.generated_at).where(
                FraudScore.generated_at >= since, FraudScore.is_fraud_predicted.is_(True))):
            buckets[generated_at.date()]["fraud_detected"] += 1
        for created_at in self.db.scalars(select(Alert.created_at).where(Alert.created_at >= since)):
            buckets[created_at.date()]["alerts"] += 1
        return [DailyTrend(date=day, **values) for day, values in buckets.items()]

    def overview(self, days: int = 30) -> DashboardOverview:
        return DashboardOverview(metrics=self.metrics(days),
            alerts_by_severity=self.distribution(Alert.severity, days),
            alerts_by_status=self.distribution(Alert.status, days), daily_trend=self.trend(days))
