"""Feature engineering service: converts enriched transaction payloads into
ML-ready feature vectors.

Feature groups
--------------
1. Amount features      – raw amount, log transform, bucket encoding, round-number flag.
2. Velocity features    – rolling-window counts and sums (5 m / 15 m / 1 h / 24 h).
3. Temporal features    – hour, day-of-week, weekend / night / business-hours flags,
                          cyclical sine/cosine encodings for hour and day-of-week.
4. Merchant features    – high-risk category flag, online merchant flag, category
                          presence.
5. Channel/Device feats – online channel, high-risk channel, card-not-present, device
                          presence.
6. Location features    – country presence, high-risk country flag, coordinates
                          presence.
7. IP features          – IP validity, private/reserved flags.
8. Customer-risk feats  – customer risk score (imputed when missing), risk-level
                          one-hot encoding.
9. Composite risk score – weighted combination of individual risk signals for quick
                          pre-filtering before the full ML model.
"""
from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Sequence

from app.utils.constants import (
    RISK_LEVEL_CRITICAL,
    RISK_LEVEL_HIGH,
    RISK_LEVEL_LOW,
    RISK_LEVEL_MEDIUM,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants / weights for composite risk scoring
# ---------------------------------------------------------------------------

_RISK_LEVEL_MAP: Dict[str, float] = {
    RISK_LEVEL_LOW: 0.1,
    RISK_LEVEL_MEDIUM: 0.4,
    RISK_LEVEL_HIGH: 0.7,
    RISK_LEVEL_CRITICAL: 1.0,
}

# Weights used in the lightweight composite risk score
_COMPOSITE_WEIGHTS: Dict[str, float] = {
    "is_night": 0.05,
    "is_weekend": 0.03,
    "is_high_risk_channel": 0.12,
    "is_high_risk_category": 0.12,
    "is_high_risk_country": 0.10,
    "is_card_not_present": 0.06,
    "ip_invalid_penalty": 0.05,
    "ip_public_bonus": 0.04,
    "amount_very_large": 0.08,
    "velocity_spike_1h": 0.15,
    "velocity_spike_24h": 0.10,
    "customer_risk_score": 0.10,
}

# ---------------------------------------------------------------------------
# FeatureEngineeringService
# ---------------------------------------------------------------------------


class FeatureEngineeringService:
    """Transform an enriched transaction dict into a flat feature vector.

    The service is stateless – no DB session is required.  All signals are
    derived from the ``enrichment`` sub-dictionary produced by
    :class:`~app.services.etl.enrichment_service.EnrichmentService`.

    If a payload has no ``enrichment`` key (i.e. enrichment was skipped) the
    service degrades gracefully, producing zero/default values for all
    enrichment-derived features.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_features(self, enriched_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Return a flat feature dict suitable for ML model input.

        Parameters
        ----------
        enriched_payload:
            Output of :meth:`EnrichmentService.enrich_transaction` or any
            transaction dict that optionally contains an ``enrichment`` key.

        Returns
        -------
        Dict[str, Any]
            Flat dictionary of named features.  All numeric values are Python
            ``float``; all binary flags are Python ``int`` (0 / 1) for
            compatibility with numpy / scikit-learn pipelines.
        """
        enrichment: Dict[str, Any] = dict(enriched_payload.get("enrichment") or {})

        features: Dict[str, Any] = {}

        # --- raw passthrough fields ---
        features["transaction_ref"] = enriched_payload.get("transaction_ref", "")
        features["customer_id"] = enriched_payload.get("customer_id", "")

        # 1. Amount features
        features.update(self._amount_features(enrichment.get("amount_signals") or {}))

        # 2. Velocity features
        features.update(self._velocity_features(enrichment.get("velocity") or {}))

        # 3. Temporal features
        features.update(self._temporal_features(enrichment.get("temporal") or {}))

        # 4. Merchant features
        features.update(self._merchant_features(enrichment.get("merchant_signals") or {}))

        # 5. Channel / device features
        features.update(
            self._device_channel_features(enrichment.get("device_channel_signals") or {})
        )

        # 6. Location features
        features.update(self._location_features(enrichment.get("location_signals") or {}))

        # 7. IP features
        features.update(self._ip_features(enrichment.get("ip_signals") or {}))

        # 8. Customer risk features
        features.update(self._customer_risk_features(enrichment.get("customer_risk") or {}))

        # 9. Composite risk score
        features["composite_risk_score"] = self._composite_risk_score(features)

        return features

    def build_features_batch(
        self,
        enriched_payloads: Sequence[Dict[str, Any]],
        skip_errors: bool = True,
    ) -> Dict[str, Any]:
        """Build feature vectors for a batch of enriched payloads.

        Returns
        -------
        Dict[str, Any]
            ``{"features": [...], "errors": [...], "summary": {...}}``
        """
        feature_records: List[Dict[str, Any]] = []
        error_records: List[Dict[str, Any]] = []

        for idx, payload in enumerate(enriched_payloads):
            try:
                feature_records.append(self.build_features(payload))
            except Exception as exc:  # noqa: BLE001
                if not skip_errors:
                    raise
                logger.warning("Feature engineering failed for record %d: %s", idx, exc)
                error_records.append({"index": idx, "error": str(exc), "payload": payload})

        return {
            "features": feature_records,
            "errors": error_records,
            "summary": {
                "total": len(enriched_payloads),
                "processed": len(feature_records),
                "failed": len(error_records),
                "feature_count": len(feature_records[0]) if feature_records else 0,
            },
        }

    def feature_names(self) -> List[str]:
        """Return the ordered list of feature names produced by :meth:`build_features`.

        Useful for building ``pandas.DataFrame`` columns or logging feature
        importance mappings.
        """
        # Build against a fully-zero payload to get the canonical key order.
        dummy = self.build_features({})
        return [k for k in dummy if k not in ("transaction_ref", "customer_id")]

    # ------------------------------------------------------------------
    # Private feature-group builders
    # ------------------------------------------------------------------

    @staticmethod
    def _amount_features(signals: Dict[str, Any]) -> Dict[str, Any]:
        amount_f: float = float(signals.get("amount_float") or 0.0)
        log_amount: float = float(signals.get("log_amount") or (math.log1p(amount_f) if amount_f >= 0 else 0.0))
        is_round: int = int(bool(signals.get("is_round_number", False)))
        bucket: str = signals.get("amount_bucket") or "small"

        return {
            "amount": round(amount_f, 2),
            "log_amount": round(log_amount, 6),
            "is_round_amount": is_round,
            # One-hot bucket encoding
            "amount_bucket_micro": int(bucket == "micro"),
            "amount_bucket_small": int(bucket == "small"),
            "amount_bucket_medium": int(bucket == "medium"),
            "amount_bucket_large": int(bucket == "large"),
            "amount_bucket_very_large": int(bucket == "very_large"),
        }

    @staticmethod
    def _velocity_features(vel: Dict[str, Any]) -> Dict[str, Any]:
        tx_5m: int = int(vel.get("tx_count_5m") or 0)
        tx_15m: int = int(vel.get("tx_count_15m") or 0)
        tx_1h: int = int(vel.get("tx_count_1h") or 0)
        tx_24h: int = int(vel.get("tx_count_24h") or 0)
        amt_sum_1h: float = float(vel.get("amount_sum_1h") or 0.0)
        amt_sum_24h: float = float(vel.get("amount_sum_24h") or 0.0)
        amt_max_24h: float = float(vel.get("amount_max_24h") or 0.0)
        merchants_24h: int = int(vel.get("unique_merchants_24h") or 0)
        channels_24h: int = int(vel.get("unique_channels_24h") or 0)

        # Spike flags (heuristic thresholds)
        velocity_spike_5m: int = int(tx_5m >= 3)
        velocity_spike_1h: int = int(tx_1h >= 10)
        velocity_spike_24h: int = int(tx_24h >= 30)

        return {
            "tx_count_5m": tx_5m,
            "tx_count_15m": tx_15m,
            "tx_count_1h": tx_1h,
            "tx_count_24h": tx_24h,
            "log_tx_count_1h": round(math.log1p(tx_1h), 6),
            "log_tx_count_24h": round(math.log1p(tx_24h), 6),
            "amount_sum_1h": round(amt_sum_1h, 2),
            "amount_sum_24h": round(amt_sum_24h, 2),
            "log_amount_sum_24h": round(math.log1p(amt_sum_24h), 6),
            "amount_max_24h": round(amt_max_24h, 2),
            "unique_merchants_24h": merchants_24h,
            "unique_channels_24h": channels_24h,
            "velocity_spike_5m": velocity_spike_5m,
            "velocity_spike_1h": velocity_spike_1h,
            "velocity_spike_24h": velocity_spike_24h,
        }

    @staticmethod
    def _temporal_features(temporal: Dict[str, Any]) -> Dict[str, Any]:
        hour: int = int(temporal.get("hour_of_day") or 0)
        dow: int = int(temporal.get("day_of_week") or 0)
        month: int = int(temporal.get("month") or 1)
        is_weekend: int = int(bool(temporal.get("is_weekend", False)))
        is_night: int = int(bool(temporal.get("is_night", False)))
        is_business_hours: int = int(bool(temporal.get("is_business_hours", False)))
        quarter_of_day: int = int(temporal.get("quarter_of_day") or 0)

        # Cyclical encoding prevents the "wrap-around" discontinuity
        hour_sin: float = round(math.sin(2 * math.pi * hour / 24), 6)
        hour_cos: float = round(math.cos(2 * math.pi * hour / 24), 6)
        dow_sin: float = round(math.sin(2 * math.pi * dow / 7), 6)
        dow_cos: float = round(math.cos(2 * math.pi * dow / 7), 6)
        month_sin: float = round(math.sin(2 * math.pi * month / 12), 6)
        month_cos: float = round(math.cos(2 * math.pi * month / 12), 6)

        return {
            "hour_of_day": hour,
            "day_of_week": dow,
            "month": month,
            "quarter_of_day": quarter_of_day,
            "is_weekend": is_weekend,
            "is_night": is_night,
            "is_business_hours": is_business_hours,
            "hour_sin": hour_sin,
            "hour_cos": hour_cos,
            "dow_sin": dow_sin,
            "dow_cos": dow_cos,
            "month_sin": month_sin,
            "month_cos": month_cos,
        }

    @staticmethod
    def _merchant_features(signals: Dict[str, Any]) -> Dict[str, Any]:
        is_high_risk: int = int(bool(signals.get("is_high_risk_category", False)))
        has_category: int = int(bool(signals.get("has_category", False)))
        is_online: int = int(bool(signals.get("is_online_merchant", False)))

        return {
            "merchant_is_high_risk_category": is_high_risk,
            "merchant_has_category": has_category,
            "merchant_is_online": is_online,
        }

    @staticmethod
    def _device_channel_features(signals: Dict[str, Any]) -> Dict[str, Any]:
        is_online_channel: int = int(bool(signals.get("is_online_channel", False)))
        is_high_risk_channel: int = int(bool(signals.get("is_high_risk_channel", False)))
        has_device: int = int(bool(signals.get("has_device_id", False)))
        is_cnp: int = int(bool(signals.get("is_card_not_present", False)))

        return {
            "channel_is_online": is_online_channel,
            "channel_is_high_risk": is_high_risk_channel,
            "channel_is_card_not_present": is_cnp,
            "has_device_id": has_device,
        }

    @staticmethod
    def _location_features(signals: Dict[str, Any]) -> Dict[str, Any]:
        has_country: int = int(bool(signals.get("has_country", False)))
        has_coords: int = int(bool(signals.get("has_coordinates", False)))
        is_high_risk_country: int = int(bool(signals.get("is_high_risk_country", False)))

        return {
            "location_has_country": has_country,
            "location_has_coordinates": has_coords,
            "location_is_high_risk_country": is_high_risk_country,
        }

    @staticmethod
    def _ip_features(signals: Dict[str, Any]) -> Dict[str, Any]:
        ip_valid: int = int(bool(signals.get("ip_valid", False)))
        ip_private: Optional[bool] = signals.get("ip_private")
        ip_reserved: Optional[bool] = signals.get("ip_reserved")

        # When IP is absent treat as neither private nor public
        ip_is_private: int = int(bool(ip_private)) if ip_valid else 0
        ip_is_public: int = int(ip_valid and not ip_private and not ip_reserved)
        ip_is_reserved: int = int(bool(ip_reserved)) if ip_valid else 0

        return {
            "ip_is_valid": ip_valid,
            "ip_is_private": ip_is_private,
            "ip_is_public": ip_is_public,
            "ip_is_reserved": ip_is_reserved,
        }

    @staticmethod
    def _customer_risk_features(risk: Dict[str, Any]) -> Dict[str, Any]:
        profile_found: int = int(bool(risk.get("profile_found", False)))
        raw_score: Optional[float] = risk.get("risk_score")
        # Impute with a moderate score (0.3) when profile not found
        risk_score: float = float(raw_score) if raw_score is not None else 0.3
        risk_level: str = (risk.get("risk_level") or RISK_LEVEL_LOW).upper()

        return {
            "customer_profile_found": profile_found,
            "customer_risk_score": round(risk_score, 4),
            # One-hot risk level
            "customer_risk_low": int(risk_level == RISK_LEVEL_LOW),
            "customer_risk_medium": int(risk_level == RISK_LEVEL_MEDIUM),
            "customer_risk_high": int(risk_level == RISK_LEVEL_HIGH),
            "customer_risk_critical": int(risk_level == RISK_LEVEL_CRITICAL),
        }

    @staticmethod
    def _composite_risk_score(features: Dict[str, Any]) -> float:
        """Compute a lightweight heuristic risk score in [0, 1].

        This is *not* a replacement for the trained ML model – it provides a
        fast pre-filter and an interpretable fallback when the model is
        unavailable.
        """
        score: float = 0.0

        score += _COMPOSITE_WEIGHTS["is_night"] * features.get("is_night", 0)
        score += _COMPOSITE_WEIGHTS["is_weekend"] * features.get("is_weekend", 0)
        score += _COMPOSITE_WEIGHTS["is_high_risk_channel"] * features.get("channel_is_high_risk", 0)
        score += _COMPOSITE_WEIGHTS["is_high_risk_category"] * features.get("merchant_is_high_risk_category", 0)
        score += _COMPOSITE_WEIGHTS["is_high_risk_country"] * features.get("location_is_high_risk_country", 0)
        score += _COMPOSITE_WEIGHTS["is_card_not_present"] * features.get("channel_is_card_not_present", 0)

        # IP penalty: invalid IP is suspicious
        if not features.get("ip_is_valid", 1):
            score += _COMPOSITE_WEIGHTS["ip_invalid_penalty"]
        # Public IP is *slightly* higher risk than private (network context)
        score += _COMPOSITE_WEIGHTS["ip_public_bonus"] * features.get("ip_is_public", 0)

        score += _COMPOSITE_WEIGHTS["amount_very_large"] * features.get("amount_bucket_very_large", 0)
        score += _COMPOSITE_WEIGHTS["velocity_spike_1h"] * features.get("velocity_spike_1h", 0)
        score += _COMPOSITE_WEIGHTS["velocity_spike_24h"] * features.get("velocity_spike_24h", 0)

        # Incorporate customer-level risk (already in [0,1])
        score += _COMPOSITE_WEIGHTS["customer_risk_score"] * features.get("customer_risk_score", 0.3)

        # Clamp to [0, 1]
        return round(min(max(score, 0.0), 1.0), 6)
