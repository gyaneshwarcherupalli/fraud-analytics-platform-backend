"""Repository helpers for persisting transaction records."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.transaction import Transaction


class TransactionRepository:
	"""Database operations for the Transaction model."""

	def __init__(self, db: Session) -> None:
		self.db = db

	def upsert_raw_transaction(
		self,
		payload: Dict[str, Any],
		kafka_metadata: Optional[Dict[str, Any]] = None,
	) -> Transaction:
		"""Insert or update a transaction using event payload fields."""
		transaction_ref = str(
			payload.get("transaction_ref")
			or payload.get("transaction_id")
			or f"TXN-{uuid4()}"
		)

		instance = self.db.execute(
			select(Transaction).where(Transaction.transaction_ref == transaction_ref)
		).scalar_one_or_none()

		resolved_amount = _parse_amount(payload.get("amount"))
		occurred_at = _parse_datetime(payload.get("occurred_at"))
		metadata = dict(payload.get("metadata") or {})
		if kafka_metadata:
			metadata["kafka"] = kafka_metadata

		if instance is None:
			instance = Transaction(
				transaction_ref=transaction_ref,
				customer_id=str(payload.get("customer_id") or "unknown-customer"),
				amount=resolved_amount,
				currency=str(payload.get("currency") or "USD")[:3],
				merchant_name=str(payload.get("merchant_name") or payload.get("merchant") or "unknown-merchant"),
				merchant_category=_optional_str(payload.get("merchant_category")),
				transaction_type=str(payload.get("transaction_type") or "purchase"),
				channel=str(payload.get("channel") or "web"),
				device_id=_optional_str(payload.get("device_id")),
				ip_address=_optional_str(payload.get("ip_address")),
				location=dict(payload.get("location") or {}),
				status=str(payload.get("status") or "received"),
				transaction_metadata=metadata,
				occurred_at=occurred_at,
			)
			self.db.add(instance)
			return instance

		instance.customer_id = str(payload.get("customer_id") or instance.customer_id)
		instance.amount = resolved_amount
		instance.currency = str(payload.get("currency") or instance.currency)[:3]
		instance.merchant_name = str(payload.get("merchant_name") or payload.get("merchant") or instance.merchant_name)
		instance.merchant_category = _optional_str(payload.get("merchant_category"))
		instance.transaction_type = str(payload.get("transaction_type") or instance.transaction_type)
		instance.channel = str(payload.get("channel") or instance.channel)
		instance.device_id = _optional_str(payload.get("device_id"))
		instance.ip_address = _optional_str(payload.get("ip_address"))
		instance.location = dict(payload.get("location") or {})
		instance.status = str(payload.get("status") or instance.status)
		instance.transaction_metadata = metadata
		instance.occurred_at = occurred_at
		return instance

	def upsert_many_raw_transactions(self, records: Iterable[Dict[str, Any]]) -> int:
		"""Persist a batch of Kafka records into transactions table."""
		stored_count = 0
		for record in records:
			value = record.get("value")
			if not isinstance(value, dict):
				continue

			kafka_metadata = {
				"topic": record.get("topic"),
				"partition": record.get("partition"),
				"offset": record.get("offset"),
				"timestamp": record.get("timestamp"),
				"key": record.get("key"),
			}
			self.upsert_raw_transaction(payload=value, kafka_metadata=kafka_metadata)
			stored_count += 1
		return stored_count


def _parse_datetime(raw_value: Any) -> datetime:
	if isinstance(raw_value, datetime):
		if raw_value.tzinfo is None:
			return raw_value.replace(tzinfo=timezone.utc)
		return raw_value

	if isinstance(raw_value, str) and raw_value:
		normalized = raw_value.replace("Z", "+00:00")
		try:
			parsed = datetime.fromisoformat(normalized)
			if parsed.tzinfo is None:
				return parsed.replace(tzinfo=timezone.utc)
			return parsed
		except ValueError:
			pass

	return datetime.now(timezone.utc)


def _optional_str(value: Any) -> Optional[str]:
	if value is None:
		return None
	casted = str(value).strip()
	return casted or None


def _parse_amount(value: Any) -> Decimal:
	try:
		return Decimal(str(value if value is not None else 0))
	except (InvalidOperation, ValueError, TypeError):
		return Decimal("0")
