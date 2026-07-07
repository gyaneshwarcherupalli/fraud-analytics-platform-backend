"""Transaction endpoints including Kafka smoke-test routes."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.ingestion.kafka_consumer import FraudKafkaConsumer
from app.services.ingestion.kafka_producer import FraudKafkaProducer
from app.services.ingestion.transaction_generator import SyntheticTransactionGenerator
from app.utils.exceptions import KafkaException


router = APIRouter(prefix="/api/transactions", tags=["transactions"])


class KafkaPublishRequest(BaseModel):
	"""Request payload for publishing a Kafka smoke-test transaction."""

	transaction_id: Optional[str] = None
	customer_id: str = "smoke-test-customer"
	amount: float = 199.99
	currency: str = "USD"
	merchant: str = "smoke-test-merchant"
	metadata: Dict[str, Any] = Field(default_factory=dict)


class KafkaPublishResponse(BaseModel):
	"""Response body for publish endpoint."""

	status: str
	topic: str
	transaction: Dict[str, Any]


class KafkaConsumeResponse(BaseModel):
	"""Response body for consume endpoint."""

	status: str
	record_count: int
	records: List[Dict[str, Any]]


class SyntheticPublishResponse(BaseModel):
	"""Response body for synthetic batch publish endpoint."""

	status: str
	topic: str
	published_count: int
	transactions: List[Dict[str, Any]]


@router.post("/kafka/smoke/publish", response_model=KafkaPublishResponse)
async def publish_smoke_transaction(payload: KafkaPublishRequest) -> KafkaPublishResponse:
	"""Publish a smoke-test transaction event to Kafka."""
	transaction_payload = {
		"transaction_id": payload.transaction_id or str(uuid4()),
		"customer_id": payload.customer_id,
		"amount": payload.amount,
		"currency": payload.currency,
		"merchant": payload.merchant,
		"metadata": payload.metadata,
		"source": "api-smoke-test",
		"created_at": datetime.now(timezone.utc).isoformat(),
	}

	producer = FraudKafkaProducer()
	try:
		producer.send_transaction(
			transaction=transaction_payload,
			key=transaction_payload["transaction_id"],
		)
		producer.flush()
	except KafkaException as exc:
		raise HTTPException(status_code=503, detail=str(exc)) from exc
	finally:
		producer.close()

	return KafkaPublishResponse(
		status="published",
		topic="transactions",
		transaction=transaction_payload,
	)


@router.get("/kafka/smoke/consume", response_model=KafkaConsumeResponse)
async def consume_smoke_transactions(
	timeout_ms: int = Query(default=1500, ge=100, le=10000),
	max_records: int = Query(default=25, ge=1, le=500),
	group_id: Optional[str] = Query(default=None),
) -> KafkaConsumeResponse:
	"""Poll Kafka transaction topic for smoke-test verification."""
	consumer = FraudKafkaConsumer(topics=["transactions"], group_id=group_id)
	try:
		records = consumer.poll_messages(timeout_ms=timeout_ms, max_records=max_records)
	except KafkaException as exc:
		raise HTTPException(status_code=503, detail=str(exc)) from exc
	finally:
		consumer.close()

	return KafkaConsumeResponse(
		status="ok",
		record_count=len(records),
		records=records,
	)


@router.post("/kafka/synthetic/publish", response_model=SyntheticPublishResponse)
async def publish_synthetic_transactions(
	count: int = Query(default=10, ge=1, le=1000),
	customer_id: Optional[str] = Query(default=None),
	delay_ms: int = Query(default=0, ge=0, le=5000),
	seed: Optional[int] = Query(default=None),
) -> SyntheticPublishResponse:
	"""Generate synthetic transactions and publish them to Kafka."""
	generator = SyntheticTransactionGenerator(seed=seed)
	try:
		transactions = generator.publish_batch(
			count=count,
			customer_id=customer_id,
			delay_ms=delay_ms,
		)
	except KafkaException as exc:
		raise HTTPException(status_code=503, detail=str(exc)) from exc

	return SyntheticPublishResponse(
		status="published",
		topic="transactions",
		published_count=len(transactions),
		transactions=transactions,
	)
