"""Database-backed fraud scoring and alert generation pipeline."""
from __future__ import annotations

from typing import Any, Dict

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.alert import Alert
from app.models.fraud_score import FraudScore
from app.models.transaction import Transaction
from app.repositories.fraud_repository import FraudRepository
from app.services.etl.enrichment_service import EnrichmentService
from app.services.fraud_engine.fraud_scoring import FraudScoringEngine
from app.utils.exceptions import DatabaseException
from app.utils.logger import get_logger
from monitoring.cloudwatch_metrics import publish_metrics_async


logger = get_logger(__name__)


def _transaction_payload(transaction: Transaction) -> Dict[str, Any]:
    return {
        "transaction_ref": transaction.transaction_ref,
        "customer_id": transaction.customer_id,
        "amount": float(transaction.amount),
        "currency": transaction.currency,
        "merchant_name": transaction.merchant_name,
        "merchant_category": transaction.merchant_category,
        "transaction_type": transaction.transaction_type,
        "channel": transaction.channel,
        "device_id": transaction.device_id,
        "ip_address": transaction.ip_address,
        "location": transaction.location or {},
        "occurred_at": transaction.occurred_at.isoformat(),
        "metadata": transaction.transaction_metadata or {},
    }


def _create_alert(db: Session, transaction: Transaction, score: FraudScore, result: Dict[str, Any]) -> None:
    severity = str(result["risk_level"]).lower()
    db.add(Alert(
        transaction_id=transaction.id,
        fraud_score_id=score.id,
        alert_type="model_fraud_prediction",
        severity=severity,
        status="open",
        title=f"{severity.title()} risk transaction detected",
        description=(
            f"Transaction {transaction.transaction_ref} scored {result['score']:.4f}. "
            f"Reasons: {', '.join(result.get('reason_codes') or ['MODEL_SCORE'])}"
        ),
    ))


def run_fraud_scoring_batch(*, batch_size: int = 250) -> Dict[str, Any]:
    """Enrich and score transactions that do not yet have a fraud score."""
    db = SessionLocal()
    try:
        transactions = list(db.execute(
            select(Transaction)
            .where(~exists().where(FraudScore.transaction_id == Transaction.id))
            .order_by(Transaction.occurred_at.asc())
            .limit(batch_size)
        ).scalars().all())
        if not transactions:
            return {"selected": 0, "scored": 0, "alerts_created": 0, "failed": 0, "status": "success"}

        engine = FraudScoringEngine()
        engine.load()
        enrichment = EnrichmentService(db)
        repository = FraudRepository(db)
        scored = 0
        alerts_created = 0
        failures = []

        for transaction in transactions:
            try:
                payload = enrichment.enrich_transaction(_transaction_payload(transaction))
                result = engine.score_transaction(payload, payload_is_enriched=True)
                score = repository.create_fraud_score(transaction.id, result)
                db.flush()
                if result["is_fraud_predicted"]:
                    _create_alert(db, transaction, score, result)
                    alerts_created += 1
                    transaction.status = "review"
                else:
                    transaction.status = "scored"
                scored += 1
            except Exception as exc:
                failures.append({"transaction_id": str(transaction.id), "error": str(exc)})
                logger.exception("Failed to score transaction %s", transaction.id)

        if failures:
            # Roll back the whole micro-batch so the next Airflow retry is deterministic.
            db.rollback()
            raise DatabaseException(f"Fraud scoring failed for {len(failures)} transaction(s)")
        db.commit()
        result = {
            "selected": len(transactions),
            "scored": scored,
            "alerts_created": alerts_created,
            "failed": 0,
            "status": "success",
        }
        logger.info("Fraud scoring batch completed: %s", result)
        publish_metrics_async([
            {"name": "TransactionsScored", "value": scored},
            {"name": "FraudDetected", "value": alerts_created},
            {"name": "AlertsCreated", "value": alerts_created},
            {"name": "PipelineSuccess", "value": 1,
             "dimensions": {"Pipeline": "FraudScoring"}},
        ])
        return result
    except Exception:
        db.rollback()
        publish_metrics_async([{"name": "PipelineFailures", "value": 1,
                                "dimensions": {"Pipeline": "FraudScoring"}}])
        raise
    finally:
        db.close()
