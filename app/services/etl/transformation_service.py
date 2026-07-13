"""Transformation service for ETL transaction payloads."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Sequence
from uuid import uuid4

from app.services.etl.validation_service import ValidationService


class TransformationService:
	"""Normalize incoming transactions into the platform canonical shape."""

	def __init__(self, validation_service: ValidationService | None = None) -> None:
		self.validation_service = validation_service or ValidationService()

	def transform_transaction(self, payload: Dict[str, Any], validate: bool = True) -> Dict[str, Any]:
		"""Transform a single payload into repository-ready transaction fields."""
		source_payload = payload.get("value") if isinstance(payload.get("value"), dict) else payload

		cleaned = (
			self.validation_service.validate_transaction(source_payload)
			if validate
			else dict(source_payload)
		)

		occurred_at = cleaned.get("occurred_at") or datetime.now(timezone.utc).isoformat()
		metadata = dict(cleaned.get("metadata") or {})
		metadata.setdefault("transformed_at", datetime.now(timezone.utc).isoformat())

		location = self._resolve_location(cleaned)

		transformed = {
			"transaction_ref": str(
				cleaned.get("transaction_ref")
				or cleaned.get("transaction_id")
				or f"TXN-{uuid4()}"
			),
			"transaction_id": cleaned.get("transaction_id"),
			"customer_id": str(cleaned.get("customer_id")),
			"amount": round(float(cleaned.get("amount", 0)), 2),
			"currency": str(cleaned.get("currency", "USD")).upper()[:3],
			"merchant_name": str(cleaned.get("merchant_name") or cleaned.get("merchant") or "unknown-merchant"),
			"merchant_category": self._optional_str(cleaned.get("merchant_category")),
			"transaction_type": str(cleaned.get("transaction_type") or "purchase").lower(),
			"channel": str(cleaned.get("channel") or "web").lower(),
			"device_id": self._optional_str(cleaned.get("device_id")),
			"ip_address": self._optional_str(cleaned.get("ip_address")),
			"location": location,
			"status": str(cleaned.get("status") or "received").lower(),
			"metadata": metadata,
			"occurred_at": occurred_at,
		}

		return transformed

	def transform_transactions_batch(
		self,
		payloads: Sequence[Dict[str, Any]],
		skip_invalid: bool = True,
	) -> Dict[str, Any]:
		"""Transform many payloads and capture invalid records for observability."""
		transformed_records: List[Dict[str, Any]] = []
		invalid_records: List[Dict[str, Any]] = []

		for index, payload in enumerate(payloads):
			try:
				transformed_records.append(self.transform_transaction(payload, validate=True))
			except Exception as exc:
				if not skip_invalid:
					raise
				invalid_records.append(
					{
						"index": index,
						"error": str(exc),
						"payload": payload,
					}
				)

		return {
			"records": transformed_records,
			"invalid_records": invalid_records,
			"summary": {
				"total": len(payloads),
				"transformed": len(transformed_records),
				"invalid": len(invalid_records),
			},
		}

	@staticmethod
	def _optional_str(value: Any) -> str | None:
		if value is None:
			return None
		casted = str(value).strip()
		return casted or None

	@staticmethod
	def _resolve_location(payload: Dict[str, Any]) -> Dict[str, Any]:
		location = payload.get("location")
		if isinstance(location, dict):
			return dict(location)

		# Support flat location payloads from simple producers.
		country = payload.get("country")
		city = payload.get("city")
		lat = payload.get("lat")
		lon = payload.get("lon")

		resolved: Dict[str, Any] = {}
		if country is not None:
			resolved["country"] = str(country)
		if city is not None:
			resolved["city"] = str(city)
		if lat is not None:
			resolved["lat"] = lat
		if lon is not None:
			resolved["lon"] = lon
		return resolved
