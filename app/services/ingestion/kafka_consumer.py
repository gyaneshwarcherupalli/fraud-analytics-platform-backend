"""Kafka consumer service for transaction and alert stream processing."""
from typing import Any, Dict, Iterable, List, Optional

from kafka.errors import KafkaError

from app.core.database import SessionLocal
from app.core.config import settings
from app.core.kafka import get_consumer
from app.repositories.transaction_repository import TransactionRepository
from app.utils.exceptions import DatabaseException
from app.utils.exceptions import KafkaException
from app.utils.logger import get_logger


logger = get_logger(__name__)


class FraudKafkaConsumer:
    """Wrapper around Kafka consumer with project defaults."""

    def __init__(self, topics: Optional[Iterable[str]] = None, group_id: Optional[str] = None) -> None:
        subscribed_topics = list(topics) if topics else [
            settings.kafka_topic_transactions,
            settings.kafka_topic_alerts,
        ]
        self._consumer = get_consumer(subscribed_topics, group_id=group_id)

    def poll_messages(self, timeout_ms: int = 1000, max_records: int = 100) -> List[Dict[str, Any]]:
        """Poll messages and return normalized records."""
        try:
            polled_data = self._consumer.poll(timeout_ms=timeout_ms, max_records=max_records)
            records: List[Dict[str, Any]] = []

            for topic_partition, messages in polled_data.items():
                for message in messages:
                    records.append(
                        {
                            "topic": topic_partition.topic,
                            "partition": topic_partition.partition,
                            "offset": message.offset,
                            "key": message.key,
                            "value": message.value,
                            "timestamp": message.timestamp,
                        }
                    )

            if records:
                logger.info("Polled %s Kafka records", len(records))
            return records
        except KafkaError as exc:
            raise KafkaException(f"Failed to poll Kafka messages: {exc}") from exc

    def commit(self) -> None:
        """Commit consumer offsets manually when auto-commit is disabled."""
        try:
            self._consumer.commit()
        except KafkaError as exc:
            raise KafkaException(f"Failed to commit Kafka offsets: {exc}") from exc

    def poll_and_store_transactions(self, timeout_ms: int = 1000, max_records: int = 100) -> Dict[str, Any]:
        """Poll transactions topic and persist records into PostgreSQL."""
        records = self.poll_messages(timeout_ms=timeout_ms, max_records=max_records)
        db = SessionLocal()
        try:
            repository = TransactionRepository(db)
            stored_count = repository.upsert_many_raw_transactions(records)
            db.commit()
            if not settings.kafka_enable_auto_commit:
                self.commit()
            return {
                "record_count": len(records),
                "stored_count": stored_count,
                "records": records,
            }
        except Exception as exc:
            db.rollback()
            raise DatabaseException(f"Failed to persist Kafka transaction records: {exc}") from exc
        finally:
            db.close()

    def close(self) -> None:
        """Close consumer resources."""
        self._consumer.close(timeout=10)

