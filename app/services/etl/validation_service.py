"""Validation service for ETL transaction payloads."""
from __future__ import annotations

from datetime import datetime
from ipaddress import ip_address
from typing import Any, Dict, List, Sequence, Tuple

from app.utils.exceptions import ValidationException


class ValidationService:
	"""Validate incoming transaction payloads before transformation/persistence."""

	REQUIRED_FIELDS = ("customer_id", "amount", "currency")

	def validate_transaction(self, payload: Dict[str, Any]) -> Dict[str, Any]:
		"""Validate and sanitize a single transaction payload.

		Raises:
			ValidationException: When one or more validation checks fail.
		"""
		errors, cleaned_payload = self._collect_errors(payload)
		if errors:
			raise ValidationException("; ".join(errors))
		return cleaned_payload

	def validate_transactions_batch(self, payloads: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
		"""Validate a list of payloads and return partitioned results."""
		valid_records: List[Dict[str, Any]] = []
		invalid_records: List[Dict[str, Any]] = []

		for index, payload in enumerate(payloads):
			errors, cleaned_payload = self._collect_errors(payload)
			if errors:
				invalid_records.append(
					{
						"index": index,
						"errors": errors,
						"payload": payload,
					}
				)
				continue
			valid_records.append(cleaned_payload)

		return {
			"valid_records": valid_records,
			"invalid_records": invalid_records,
			"summary": {
				"total": len(payloads),
				"valid": len(valid_records),
				"invalid": len(invalid_records),
			},
		}

	def _collect_errors(self, payload: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
		if not isinstance(payload, dict):
			return ["Payload must be a dictionary."], {}

		errors: List[str] = []
		cleaned = dict(payload)

		for field in self.REQUIRED_FIELDS:
			value = cleaned.get(field)
			if value is None or (isinstance(value, str) and not value.strip()):
				errors.append(f"Missing required field '{field}'.")

		customer_id = cleaned.get("customer_id")
		if customer_id is not None:
			customer_id_str = str(customer_id).strip()
			if not customer_id_str:
				errors.append("'customer_id' must be a non-empty value.")
			else:
				cleaned["customer_id"] = customer_id_str

		amount = cleaned.get("amount")
		if amount is not None:
			try:
				amount_value = float(amount)
				if amount_value <= 0:
					errors.append("'amount' must be greater than 0.")
				else:
					cleaned["amount"] = round(amount_value, 2)
			except (TypeError, ValueError):
				errors.append("'amount' must be a valid number.")

		currency = cleaned.get("currency")
		if currency is not None:
			currency_value = str(currency).strip().upper()
			if len(currency_value) != 3 or not currency_value.isalpha():
				errors.append("'currency' must be a 3-letter ISO code.")
			else:
				cleaned["currency"] = currency_value

		merchant_name = cleaned.get("merchant_name") or cleaned.get("merchant")
		if merchant_name is not None:
			merchant_name_value = str(merchant_name).strip()
			if not merchant_name_value:
				errors.append("'merchant_name'/'merchant' cannot be empty when provided.")
			else:
				cleaned["merchant_name"] = merchant_name_value

		occurred_at = cleaned.get("occurred_at")
		if occurred_at is not None:
			parsed_time = self._parse_datetime(occurred_at)
			if parsed_time is None:
				errors.append("'occurred_at' must be a valid ISO-8601 datetime string.")
			else:
				cleaned["occurred_at"] = parsed_time.isoformat()

		ip_value = cleaned.get("ip_address")
		if ip_value is not None and str(ip_value).strip():
			try:
				ip_address(str(ip_value).strip())
				cleaned["ip_address"] = str(ip_value).strip()
			except ValueError:
				errors.append("'ip_address' must be a valid IPv4 or IPv6 address.")

		metadata = cleaned.get("metadata")
		if metadata is not None and not isinstance(metadata, dict):
			errors.append("'metadata' must be a dictionary when provided.")

		location = cleaned.get("location")
		if location is not None:
			if not isinstance(location, dict):
				errors.append("'location' must be a dictionary when provided.")
			else:
				lat = location.get("lat")
				lon = location.get("lon")
				if lat is not None:
					try:
						lat_value = float(lat)
						if lat_value < -90 or lat_value > 90:
							errors.append("'location.lat' must be between -90 and 90.")
					except (TypeError, ValueError):
						errors.append("'location.lat' must be numeric when provided.")
				if lon is not None:
					try:
						lon_value = float(lon)
						if lon_value < -180 or lon_value > 180:
							errors.append("'location.lon' must be between -180 and 180.")
					except (TypeError, ValueError):
						errors.append("'location.lon' must be numeric when provided.")

		return errors, cleaned

	@staticmethod
	def _parse_datetime(value: Any) -> datetime | None:
		if isinstance(value, datetime):
			return value

		if isinstance(value, str):
			raw = value.strip()
			if not raw:
				return None
			normalized = raw.replace("Z", "+00:00")
			try:
				return datetime.fromisoformat(normalized)
			except ValueError:
				return None

		return None
