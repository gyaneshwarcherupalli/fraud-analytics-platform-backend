"""
Kafka core utilities for connection setup, topic initialization,
and producer/consumer configuration.
"""
import json
import time
from typing import Any, Dict, Iterable, Optional

from kafka import KafkaAdminClient, KafkaConsumer, KafkaProducer
from kafka.admin import NewTopic
from kafka.errors import KafkaError, TopicAlreadyExistsError

from app.core.config import settings
from app.utils.exceptions import KafkaException
from app.utils.logger import get_logger


logger = get_logger(__name__)


def _serialize_value(value: Any) -> bytes:
    """Serialize Python objects to JSON bytes for Kafka messages."""
    return json.dumps(value).encode("utf-8")


def _deserialize_value(value: Optional[bytes]) -> Any:
    """Deserialize Kafka bytes payload into Python objects."""
    if value is None:
        return None
    return json.loads(value.decode("utf-8"))


def producer_config(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Build default producer configuration with optional overrides."""
    config: Dict[str, Any] = {
        "bootstrap_servers": settings.kafka_broker,
        "client_id": settings.kafka_client_id,
        "acks": settings.kafka_producer_acks,
        "retries": settings.kafka_producer_retries,
        "batch_size": settings.kafka_producer_batch_size,
        "linger_ms": settings.kafka_producer_linger_ms,
        "compression_type": settings.kafka_producer_compression_type,
        "value_serializer": _serialize_value,
        "key_serializer": lambda key: str(key).encode("utf-8") if key is not None else None,
    }
    if overrides:
        config.update(overrides)
    return config


def consumer_config(
    group_id: Optional[str] = None,
    overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build default consumer configuration with optional overrides."""
    config: Dict[str, Any] = {
        "bootstrap_servers": settings.kafka_broker,
        "client_id": settings.kafka_client_id,
        "group_id": group_id or settings.kafka_consumer_group,
        "auto_offset_reset": settings.kafka_auto_offset_reset,
        "enable_auto_commit": settings.kafka_enable_auto_commit,
        "auto_commit_interval_ms": settings.kafka_auto_commit_interval_ms,
        "max_poll_records": settings.kafka_max_poll_records,
        "value_deserializer": _deserialize_value,
        "key_deserializer": lambda key: key.decode("utf-8") if key is not None else None,
    }
    if overrides:
        config.update(overrides)
    return config


def get_producer(overrides: Optional[Dict[str, Any]] = None) -> KafkaProducer:
    """Create and return a configured Kafka producer."""
    try:
        return KafkaProducer(**producer_config(overrides))
    except KafkaError as exc:
        raise KafkaException(f"Failed to initialize Kafka producer: {exc}") from exc


def get_consumer(
    topics: Iterable[str],
    group_id: Optional[str] = None,
    overrides: Optional[Dict[str, Any]] = None,
) -> KafkaConsumer:
    """Create and return a configured Kafka consumer subscribed to topics."""
    try:
        return KafkaConsumer(*topics, **consumer_config(group_id, overrides))
    except KafkaError as exc:
        raise KafkaException(f"Failed to initialize Kafka consumer: {exc}") from exc


def ensure_topics_exist(topics: Optional[Iterable[str]] = None, retries: int = 5, delay_seconds: int = 2) -> None:
    """Create required topics if they are missing."""
    topics_to_create = list(topics) if topics else settings.kafka_topics
    attempts = 0

    while attempts < retries:
        attempts += 1
        admin_client: Optional[KafkaAdminClient] = None
        try:
            admin_client = KafkaAdminClient(
                bootstrap_servers=settings.kafka_broker,
                client_id=f"{settings.kafka_client_id}-admin",
            )

            existing_topics = set(admin_client.list_topics())
            new_topics = [
                NewTopic(
                    name=topic,
                    num_partitions=settings.kafka_topic_partitions,
                    replication_factor=settings.kafka_topic_replication_factor,
                )
                for topic in topics_to_create
                if topic not in existing_topics
            ]

            if not new_topics:
                logger.info("Kafka topics already exist: %s", topics_to_create)
                return

            admin_client.create_topics(new_topics=new_topics, validate_only=False)
            logger.info("Created Kafka topics: %s", [topic.name for topic in new_topics])
            return
        except TopicAlreadyExistsError:
            logger.info("Kafka topic creation skipped: topics already exist.")
            return
        except KafkaError as exc:
            if attempts >= retries:
                raise KafkaException(
                    f"Failed to ensure Kafka topics after {retries} attempts: {exc}"
                ) from exc
            logger.warning(
                "Kafka unavailable while creating topics (attempt %s/%s). Retrying in %ss.",
                attempts,
                retries,
                delay_seconds,
            )
            time.sleep(delay_seconds)
        finally:
            if admin_client:
                admin_client.close()

