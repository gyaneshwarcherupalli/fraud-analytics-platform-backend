"""Enrichment service: augments raw transaction payloads with contextual signals.

Enrichment pipeline
-------------------
1. Customer risk profile  – pull stored risk score / factors from DB.
2. Velocity metrics       – count / sum of transactions in rolling time windows.
3. Temporal features      – hour-of-day, day-of-week, weekend / night flags.
4. IP geo-context         – private / reserved range detection; optional ARIN-style
                            block labeling (no external HTTP call required).
5. Merchant context       – normalise category, build merchant familiarity flag.
6. Device / channel risk  – mark high-risk channels and missing device signals.
"""
from __future__ import annotations

import ipaddress
import logging
import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.customer_risk import CustomerRisk
from app.models.transaction import Transaction
from app.utils.constants import (
    RISK_LEVEL_HIGH,
    RISK_LEVEL_LOW,
    RISK_LEVEL_MEDIUM,
    RISK_LEVEL_CRITICAL,
    TIME_WINDOW_1_HOUR,
    TIME_WINDOW_24_HOURS,
    TIME_WINDOW_5_MINUTES,
    TIME_WINDOW_15_MINUTES,
)
from app.utils.exceptions import FraudAnalyticsException

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_HIGH_RISK_CHANNELS = {"atm", "pos_abroad", "international_wire", "crypto"}
_ROUND_AMOUNT_TOLERANCE = Decimal("0.01")

# Merchant categories that are statistically associated with higher fraud rates
_HIGH_RISK_MERCHANT_CATEGORIES = {
    "cryptocurrency",
    "gambling",
    "money_transfer",
    "forex",
    "prepaid_cards",
    "wire_transfer",
    "adult_entertainment",
    "online_gaming",
}

# Channels considered fully online / card-not-present
_ONLINE_CHANNELS = {"web", "mobile", "api", "ecommerce"}


def _parse_occurred_at(value: Any) -> datetime:
    """Return timezone-aware datetime from string or datetime."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _classify_ip(ip_str: Optional[str]) -> Dict[str, Any]:
    """Return basic IP metadata without external lookups."""
    if not ip_str:
        return {"ip_valid": False, "ip_private": None, "ip_version": None, "ip_reserved": None}
    try:
        addr = ipaddress.ip_address(ip_str.strip())
        return {
            "ip_valid": True,
            "ip_version": addr.version,
            "ip_private": addr.is_private,
            "ip_reserved": addr.is_reserved or addr.is_loopback or addr.is_link_local,
        }
    except ValueError:
        return {"ip_valid": False, "ip_private": None, "ip_version": None, "ip_reserved": None}


# ---------------------------------------------------------------------------
# EnrichmentService
# ---------------------------------------------------------------------------


class EnrichmentService:
    """Enriches a transaction payload dictionary with contextual signals.

    Parameters
    ----------
    db:
        SQLAlchemy ``Session`` used to query historical data. When ``None`` the
        service operates in *stateless* mode (no DB-backed enrichment).
    """

    def __init__(self, db: Optional[Session] = None) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enrich_transaction(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Return a copy of *payload* augmented with enrichment signals.

        The returned dictionary preserves all original keys and adds an
        ``enrichment`` top-level key containing the computed signals.

        Parameters
        ----------
        payload:
            Transformed transaction dict (output of ``TransformationService``).

        Returns
        -------
        Dict[str, Any]
            Enriched payload with an ``enrichment`` key.
        """
        enriched = dict(payload)
        customer_id: str = str(payload.get("customer_id", ""))
        occurred_at: datetime = _parse_occurred_at(payload.get("occurred_at"))
        amount = Decimal(str(payload.get("amount", 0)))
        channel: str = str(payload.get("channel", "")).lower()
        ip_address: Optional[str] = payload.get("ip_address")
        merchant_name: str = str(payload.get("merchant_name", "")).lower()
        merchant_category: Optional[str] = payload.get("merchant_category")
        device_id: Optional[str] = payload.get("device_id")
        location: Dict[str, Any] = dict(payload.get("location") or {})
        transaction_ref: str = str(payload.get("transaction_ref", ""))

        enrichment: Dict[str, Any] = {}

        # 1. Customer risk profile
        enrichment["customer_risk"] = self._enrich_customer_risk(customer_id)

        # 2. Velocity metrics
        enrichment["velocity"] = self._compute_velocity(
            customer_id=customer_id,
            occurred_at=occurred_at,
            current_amount=amount,
            current_ref=transaction_ref,
        )

        # 3. Temporal signals
        enrichment["temporal"] = self._compute_temporal(occurred_at)

        # 4. IP signals
        enrichment["ip_signals"] = _classify_ip(ip_address)

        # 5. Merchant signals
        enrichment["merchant_signals"] = self._enrich_merchant(merchant_name, merchant_category)

        # 6. Device / channel signals
        enrichment["device_channel_signals"] = self._enrich_device_channel(channel, device_id)

        # 7. Location signals
        enrichment["location_signals"] = self._enrich_location(location)

        # 8. Amount signals
        enrichment["amount_signals"] = self._enrich_amount(amount)

        enrichment["enriched_at"] = datetime.now(timezone.utc).isoformat()

        enriched["enrichment"] = enrichment
        return enriched

    def enrich_transactions_batch(
        self,
        payloads: Sequence[Dict[str, Any]],
        skip_errors: bool = True,
    ) -> Dict[str, Any]:
        """Enrich a batch of transaction payloads.

        Parameters
        ----------
        payloads:
            Iterable of transformed transaction dicts.
        skip_errors:
            When ``True``, individual enrichment failures are captured and the
            batch continues.  When ``False``, the first error is re-raised.

        Returns
        -------
        Dict[str, Any]
            ``{"enriched": [...], "errors": [...], "summary": {...}}``
        """
        enriched_records: List[Dict[str, Any]] = []
        error_records: List[Dict[str, Any]] = []

        for idx, payload in enumerate(payloads):
            try:
                enriched_records.append(self.enrich_transaction(payload))
            except Exception as exc:  # noqa: BLE001
                if not skip_errors:
                    raise
                logger.warning("Enrichment failed for record %d: %s", idx, exc)
                error_records.append({"index": idx, "error": str(exc), "payload": payload})

        return {
            "enriched": enriched_records,
            "errors": error_records,
            "summary": {
                "total": len(payloads),
                "enriched": len(enriched_records),
                "failed": len(error_records),
            },
        }

    # ------------------------------------------------------------------
    # Private enrichment helpers
    # ------------------------------------------------------------------

    def _enrich_customer_risk(self, customer_id: str) -> Dict[str, Any]:
        """Return customer risk profile from DB or a default when unavailable."""
        default: Dict[str, Any] = {
            "risk_score": None,
            "risk_level": None,
            "risk_factors": {},
            "last_evaluated_at": None,
            "profile_found": False,
        }
        if not self.db or not customer_id:
            return default
        try:
            row = self.db.execute(
                select(CustomerRisk).where(CustomerRisk.customer_id == customer_id)
            ).scalar_one_or_none()
            if row is None:
                return default
            return {
                "risk_score": float(row.risk_score),
                "risk_level": row.risk_level,
                "risk_factors": dict(row.risk_factors or {}),
                "last_evaluated_at": (
                    row.last_evaluated_at.isoformat() if row.last_evaluated_at else None
                ),
                "profile_found": True,
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not fetch customer risk for %s: %s", customer_id, exc)
            return default

    def _compute_velocity(
        self,
        customer_id: str,
        occurred_at: datetime,
        current_amount: Decimal,
        current_ref: str,
    ) -> Dict[str, Any]:
        """Compute rolling-window transaction velocity metrics from DB."""
        empty: Dict[str, Any] = {
            "tx_count_5m": 0,
            "tx_count_15m": 0,
            "tx_count_1h": 0,
            "tx_count_24h": 0,
            "amount_sum_1h": 0.0,
            "amount_sum_24h": 0.0,
            "amount_max_24h": 0.0,
            "unique_merchants_24h": 0,
            "unique_channels_24h": 0,
        }
        if not self.db or not customer_id:
            return empty

        windows: List[Tuple[str, int]] = [
            ("5m", TIME_WINDOW_5_MINUTES),
            ("15m", TIME_WINDOW_15_MINUTES),
            ("1h", TIME_WINDOW_1_HOUR),
            ("24h", TIME_WINDOW_24_HOURS),
        ]

        results: Dict[str, Any] = {}
        try:
            for label, seconds in windows:
                since = occurred_at - timedelta(seconds=seconds)
                base_q = select(Transaction).where(
                    Transaction.customer_id == customer_id,
                    Transaction.occurred_at >= since,
                    Transaction.occurred_at <= occurred_at,
                )
                if current_ref:
                    base_q = base_q.where(Transaction.transaction_ref != current_ref)

                rows: List[Transaction] = list(self.db.execute(base_q).scalars().all())
                results[f"tx_count_{label}"] = len(rows)

                if label in ("1h", "24h"):
                    amounts = [float(r.amount) for r in rows]
                    results[f"amount_sum_{label}"] = round(sum(amounts), 2)
                    if label == "24h":
                        results["amount_max_24h"] = round(max(amounts, default=0.0), 2)
                        results["unique_merchants_24h"] = len({r.merchant_name for r in rows})
                        results["unique_channels_24h"] = len({r.channel for r in rows})
        except Exception as exc:  # noqa: BLE001
            logger.warning("Velocity computation failed for %s: %s", customer_id, exc)
            return empty

        return results

    @staticmethod
    def _compute_temporal(occurred_at: datetime) -> Dict[str, Any]:
        """Derive time-based signals from the transaction timestamp."""
        hour = occurred_at.hour
        dow = occurred_at.weekday()  # 0 = Monday … 6 = Sunday
        is_weekend = dow >= 5
        # Night window: 22:00 – 05:59
        is_night = hour >= 22 or hour < 6
        # Business hours: Mon-Fri 09:00-17:59
        is_business_hours = (not is_weekend) and (9 <= hour < 18)

        quarter_of_day: int = hour // 6  # 0=night, 1=morning, 2=afternoon, 3=evening

        return {
            "hour_of_day": hour,
            "day_of_week": dow,
            "day_of_week_name": occurred_at.strftime("%A"),
            "month": occurred_at.month,
            "is_weekend": is_weekend,
            "is_night": is_night,
            "is_business_hours": is_business_hours,
            "quarter_of_day": quarter_of_day,
            "week_of_year": occurred_at.isocalendar()[1],
        }

    @staticmethod
    def _enrich_merchant(
        merchant_name: str, merchant_category: Optional[str]
    ) -> Dict[str, Any]:
        """Derive merchant-level risk signals."""
        category_lower = (merchant_category or "").lower().strip()
        is_high_risk_category = category_lower in _HIGH_RISK_MERCHANT_CATEGORIES
        has_category = bool(category_lower)
        is_online_merchant = any(
            kw in merchant_name for kw in ("online", "web", "digital", "cyber", "virtual", ".com")
        )

        return {
            "category_normalised": category_lower or None,
            "is_high_risk_category": is_high_risk_category,
            "has_category": has_category,
            "is_online_merchant": is_online_merchant,
        }

    @staticmethod
    def _enrich_device_channel(channel: str, device_id: Optional[str]) -> Dict[str, Any]:
        """Derive device and channel risk signals."""
        is_online_channel = channel in _ONLINE_CHANNELS
        is_high_risk_channel = channel in _HIGH_RISK_CHANNELS
        has_device_id = device_id is not None and str(device_id).strip() != ""

        return {
            "channel_normalised": channel or None,
            "is_online_channel": is_online_channel,
            "is_high_risk_channel": is_high_risk_channel,
            "has_device_id": has_device_id,
            "is_card_not_present": is_online_channel,
        }

    @staticmethod
    def _enrich_location(location: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and normalise location signals."""
        country = str(location.get("country") or "").upper().strip()
        city = str(location.get("city") or "").strip()
        has_country = bool(country)
        has_coordinates = (
            location.get("latitude") is not None and location.get("longitude") is not None
        )

        # Simple high-risk country heuristic (FATF greylist / typical fraud hotspots)
        _HIGH_RISK_COUNTRIES = {
            "NG", "GH", "RU", "CN", "UA", "RO", "BR", "PK", "BD", "VN",
        }
        is_high_risk_country = country in _HIGH_RISK_COUNTRIES

        return {
            "country": country or None,
            "city": city or None,
            "has_country": has_country,
            "has_coordinates": has_coordinates,
            "is_high_risk_country": is_high_risk_country,
        }

    @staticmethod
    def _enrich_amount(amount: Decimal) -> Dict[str, Any]:
        """Derive amount-level signals."""
        amount_f = float(amount)
        is_round_number = (amount % 1) < float(_ROUND_AMOUNT_TOLERANCE)
        log_amount = math.log1p(amount_f) if amount_f >= 0 else 0.0

        # Bucket the amount for categorical lookups
        if amount_f < 10:
            amount_bucket = "micro"
        elif amount_f < 100:
            amount_bucket = "small"
        elif amount_f < 1_000:
            amount_bucket = "medium"
        elif amount_f < 10_000:
            amount_bucket = "large"
        else:
            amount_bucket = "very_large"

        return {
            "amount_float": round(amount_f, 2),
            "log_amount": round(log_amount, 6),
            "is_round_number": is_round_number,
            "amount_bucket": amount_bucket,
        }
