"""Kafka producer service for transaction and alert event publishing."""
from typing import Any, Dict, Optional

from kafka.errors import KafkaError

from app.core.config import settings
from app.core.kafka import get_producer
from app.utils.exceptions import KafkaException
from app.utils.logger import get_logger


logger = get_logger(__name__)


class FraudKafkaProducer:
    """Wrapper around Kafka producer with project defaults."""

    def __init__(self) -> None:
        self._producer = get_producer()

    def send_message(self, topic: str, payload: Dict[str, Any], key: Optional[str] = None) -> None:
        """Publish a payload to a target topic and wait for delivery result."""
        try:
            future = self._producer.send(topic=topic, key=key, value=payload)
            metadata = future.get(timeout=10)
            logger.info(
                "Published message to topic=%s partition=%s offset=%s",
                metadata.topic,
                metadata.partition,
                metadata.offset,
            )
        except KafkaError as exc:
            raise KafkaException(f"Failed to send message to topic '{topic}': {exc}") from exc

    def send_transaction(self, transaction: Dict[str, Any], key: Optional[str] = None) -> None:
        """Publish a transaction event to the transactions topic."""
        self.send_message(settings.kafka_topic_transactions, transaction, key=key)

    def send_transactions(self, transactions: list[Dict[str, Any]]) -> None:
        """Publish multiple transaction events and flush once for efficiency."""
        for transaction in transactions:
            transaction_key = transaction.get("transaction_id")
            self.send_transaction(transaction=transaction, key=transaction_key)
        self.flush()

    def send_alert(self, alert: Dict[str, Any], key: Optional[str] = None) -> None:
        """Publish an alert event to the alerts topic."""
        self.send_message(settings.kafka_topic_alerts, alert, key=key)

    def flush(self) -> None:
        """Flush producer buffer."""
        self._producer.flush(timeout=10)

    def close(self) -> None:
        """Flush and close producer resources."""
        self._producer.flush(timeout=10)
        self._producer.close(timeout=10)

