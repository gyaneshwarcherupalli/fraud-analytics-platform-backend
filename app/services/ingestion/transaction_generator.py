"""Synthetic transaction generator used for Kafka ingestion testing."""
from __future__ import annotations

import random
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.services.ingestion.kafka_producer import FraudKafkaProducer
from app.utils.exceptions import KafkaException
from app.utils.logger import get_logger


logger = get_logger(__name__)


class SyntheticTransactionGenerator:
	"""Generate deterministic-shape synthetic transaction events for Kafka topics."""

	_currencies = ["USD", "EUR", "GBP", "CAD", "AED", "JPY"]
	_channels = ["web", "mobile", "pos", "atm"]
	_transaction_types = ["purchase", "withdrawal", "transfer", "refund"]
	_merchant_categories = [
		"grocery",
		"electronics",
		"travel",
		"gaming",
		"fuel",
		"healthcare",
		"luxury",
	]
	_countries = ["US", "GB", "DE", "AE", "IN", "CA", "JP", "BR"]

	def __init__(self, seed: Optional[int] = None) -> None:
		self._random = random.Random(seed)

	def generate_transaction(self, customer_id: Optional[str] = None) -> Dict[str, Any]:
		"""Generate one synthetic transaction payload."""
		amount = round(self._random.lognormvariate(3.5, 1.1), 2)
		is_high_risk = amount > 1000 or self._random.random() < 0.08

		country = self._random.choice(self._countries)
		channel = self._random.choice(self._channels)

		transaction_id = str(uuid4())
		resolved_customer_id = customer_id or f"customer-{self._random.randint(1000, 9999)}"

		payload: Dict[str, Any] = {
			"transaction_id": transaction_id,
			"transaction_ref": f"TXN-{int(time.time() * 1000)}-{self._random.randint(100, 999)}",
			"customer_id": resolved_customer_id,
			"amount": amount,
			"currency": self._random.choice(self._currencies),
			"merchant": f"merchant-{self._random.randint(1, 250)}",
			"merchant_category": self._random.choice(self._merchant_categories),
			"transaction_type": self._random.choice(self._transaction_types),
			"channel": channel,
			"device_id": f"device-{self._random.randint(10000, 99999)}",
			"ip_address": self._generate_ip_address(),
			"location": {
				"country": country,
				"city": f"city-{self._random.randint(1, 500)}",
				"lat": round(self._random.uniform(-90, 90), 6),
				"lon": round(self._random.uniform(-180, 180), 6),
			},
			"status": "received",
			"metadata": {
				"synthetic": True,
				"risk_hint": "high" if is_high_risk else "normal",
				"source": "transaction-generator",
			},
			"occurred_at": datetime.now(timezone.utc).isoformat(),
			"created_at": datetime.now(timezone.utc).isoformat(),
		}

		return payload

	def generate_batch(self, count: int, customer_id: Optional[str] = None) -> List[Dict[str, Any]]:
		"""Generate a batch of synthetic transactions."""
		if count <= 0:
			return []
		return [self.generate_transaction(customer_id=customer_id) for _ in range(count)]

	def publish_batch(
		self,
		count: int,
		customer_id: Optional[str] = None,
		delay_ms: int = 0,
	) -> List[Dict[str, Any]]:
		"""Generate and publish transactions to Kafka transactions topic."""
		transactions = self.generate_batch(count=count, customer_id=customer_id)
		if not transactions:
			return transactions

		producer = FraudKafkaProducer()
		try:
			for transaction in transactions:
				producer.send_transaction(
					transaction=transaction,
					key=transaction["transaction_id"],
				)
				if delay_ms > 0:
					time.sleep(delay_ms / 1000)
			producer.flush()
			logger.info("Published %s synthetic transaction events", len(transactions))
		except KafkaException:
			raise
		finally:
			producer.close()

		return transactions

	def _generate_ip_address(self) -> str:
		return ".".join(str(self._random.randint(1, 254)) for _ in range(4))
