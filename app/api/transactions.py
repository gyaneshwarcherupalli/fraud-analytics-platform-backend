"""Transaction endpoints including Kafka smoke-test routes."""
from datetime import datetime, timezone
from math import ceil
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.transaction_repository import TransactionRepository
from app.schemas.transaction_schema import (
    TransactionCreate,
    TransactionListResponse,
    TransactionResponse,
    TransactionStatusUpdate,
)
from app.services.ingestion.kafka_consumer import FraudKafkaConsumer
from app.services.ingestion.kafka_producer import FraudKafkaProducer
from app.services.ingestion.transaction_generator import SyntheticTransactionGenerator
from app.utils.exceptions import DatabaseException
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
	stored_count: int
	records: List[Dict[str, Any]]


class SyntheticPublishResponse(BaseModel):
	"""Response body for synthetic batch publish endpoint."""

	status: str
	topic: str
	published_count: int
	transactions: List[Dict[str, Any]]


# ---------------------------------------------------------------------------
# CRUD endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=TransactionResponse, status_code=201, summary="Create transaction")
async def create_transaction(
    payload: TransactionCreate,
    db: Session = Depends(get_db),
) -> TransactionResponse:
    """Persist a new transaction record directly via the REST API."""
    repo = TransactionRepository(db)
    raw: Dict[str, Any] = payload.model_dump()
    raw.setdefault("transaction_ref", f"TXN-{uuid4()}")
    if raw.get("occurred_at") is None:
        raw["occurred_at"] = datetime.now(timezone.utc).isoformat()
    try:
        instance = repo.upsert_raw_transaction(raw)
        db.commit()
        db.refresh(instance)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return TransactionResponse.model_validate(instance)


@router.get("", response_model=TransactionListResponse, summary="List transactions")
async def list_transactions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    customer_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> TransactionListResponse:
    """Return a paginated list of transactions with optional filters."""
    repo = TransactionRepository(db)
    items, total = repo.list_transactions(
        page=page,
        page_size=page_size,
        customer_id=customer_id,
        status=status,
    )
    return TransactionListResponse(
        items=[TransactionResponse.model_validate(t) for t in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=ceil(total / page_size) if page_size else 1,
    )


@router.get("/{transaction_id}", response_model=TransactionResponse, summary="Get transaction by ID")
async def get_transaction(
    transaction_id: UUID,
    db: Session = Depends(get_db),
) -> TransactionResponse:
    """Return a single transaction by its UUID primary key."""
    repo = TransactionRepository(db)
    instance = repo.get_by_id(transaction_id)
    if instance is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return TransactionResponse.model_validate(instance)


@router.patch("/{transaction_id}/status", response_model=TransactionResponse, summary="Update transaction status")
async def update_transaction_status(
    transaction_id: UUID,
    payload: TransactionStatusUpdate,
    db: Session = Depends(get_db),
) -> TransactionResponse:
    """Update the processing status of an existing transaction."""
    repo = TransactionRepository(db)
    instance = repo.update_status(transaction_id, payload.status)
    if instance is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    try:
        db.commit()
        db.refresh(instance)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return TransactionResponse.model_validate(instance)


# ---------------------------------------------------------------------------
# Kafka smoke-test / ingestion endpoints
# ---------------------------------------------------------------------------

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
	"""Poll Kafka transactions and persist raw records into PostgreSQL."""
	consumer = FraudKafkaConsumer(topics=["transactions"], group_id=group_id)
	try:
		result = consumer.poll_and_store_transactions(timeout_ms=timeout_ms, max_records=max_records)
	except KafkaException as exc:
		raise HTTPException(status_code=503, detail=str(exc)) from exc
	except DatabaseException as exc:
		raise HTTPException(status_code=500, detail=str(exc)) from exc
	finally:
		consumer.close()

	return KafkaConsumeResponse(
		status="ok",
		record_count=result["record_count"],
		stored_count=result["stored_count"],
		records=result["records"],
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
	stored_count: int
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
	"""Poll Kafka transactions and persist raw records into PostgreSQL."""
	consumer = FraudKafkaConsumer(topics=["transactions"], group_id=group_id)
	try:
		result = consumer.poll_and_store_transactions(timeout_ms=timeout_ms, max_records=max_records)
	except KafkaException as exc:
		raise HTTPException(status_code=503, detail=str(exc)) from exc
	except DatabaseException as exc:
		raise HTTPException(status_code=500, detail=str(exc)) from exc
	finally:
		consumer.close()

	return KafkaConsumeResponse(
		status="ok",
		record_count=result["record_count"],
		stored_count=result["stored_count"],
		records=result["records"],
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
