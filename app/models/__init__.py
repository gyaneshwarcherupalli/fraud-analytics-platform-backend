"""SQLAlchemy model registry for metadata discovery."""

from app.models.alert import Alert
from app.models.customer_risk import CustomerRisk
from app.models.fraud_score import FraudScore
from app.models.investigation import Investigation
from app.models.transaction import Transaction

__all__ = [
    "Alert",
    "CustomerRisk",
    "FraudScore",
    "Investigation",
    "Transaction",
]
