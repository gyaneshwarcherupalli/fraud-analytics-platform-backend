"""Kafka-to-PostgreSQL transaction ingestion pipeline."""
from __future__ import annotations

from typing import Any, Dict

from app.core.config import settings
from app.core.database import SessionLocal
from app.repositories.transaction_repository import TransactionRepository
from app.services.etl.transformation_service import TransformationService
from app.services.ingestion.kafka_consumer import FraudKafkaConsumer
from app.utils.exceptions import DatabaseException
from app.utils.logger import get_logger


logger = get_logger(__name__)


def run_ingestion_batch(
    *,
    timeout_ms: int = 5000,
    max_records: int | None = None,
    group_id: str = "fraud-airflow-ingestion",
) -> Dict[str, Any]:
    """Poll, validate, transform, and persist one Kafka micro-batch.

    Consumer offsets are committed only after the database transaction succeeds,
    making retries safe because transaction references are upserted.
    """
    batch_size = max_records or settings.kafka_max_poll_records
    consumer = FraudKafkaConsumer(topics=[settings.kafka_topic_transactions], group_id=group_id)
    db = SessionLocal()
    try:
        records = consumer.poll_messages(timeout_ms=timeout_ms, max_records=batch_size)
        transformer = TransformationService()
        repository = TransactionRepository(db)
        stored = 0
        invalid = 0

        for record in records:
            payload = record.get("value")
            if not isinstance(payload, dict):
                invalid += 1
                continue
            try:
                transformed = transformer.transform_transaction(payload)
            except Exception as exc:  # invalid events should not fail the batch
                invalid += 1
                logger.warning("Skipping invalid Kafka record at offset %s: %s", record.get("offset"), exc)
                continue

            kafka_metadata = {
                "topic": record.get("topic"),
                "partition": record.get("partition"),
                "offset": record.get("offset"),
                "timestamp": record.get("timestamp"),
                "key": record.get("key"),
            }
            repository.upsert_raw_transaction(transformed, kafka_metadata=kafka_metadata)
            stored += 1

        db.commit()
        if records and not settings.kafka_enable_auto_commit:
            consumer.commit()
        result = {
            "polled": len(records),
            "stored": stored,
            "invalid": invalid,
            "status": "success",
        }
        logger.info("Ingestion batch completed: %s", result)
        return result
    except Exception as exc:
        db.rollback()
        if isinstance(exc, DatabaseException):
            raise
        raise DatabaseException(f"Ingestion pipeline failed: {exc}") from exc
    finally:
        db.close()
        consumer.close()
