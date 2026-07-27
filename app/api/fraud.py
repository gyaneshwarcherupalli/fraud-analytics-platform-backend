"""Fraud scoring and risk endpoints."""
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter
from pydantic import BaseModel, Field


router = APIRouter(prefix="/api/fraud", tags=["fraud"])


class FraudScoreResponse(BaseModel):
	"""Simple fraud score response used for API smoke tests."""

	score: float = Field(ge=0, le=100)
	risk_level: str
	generated_at: str
	metadata: Dict[str, Any] = Field(default_factory=dict)


@router.get("/score/sample", response_model=FraudScoreResponse, summary="Get sample fraud score")
async def get_sample_fraud_score() -> FraudScoreResponse:
	"""Return a static score response until model serving endpoints are added."""
	return FraudScoreResponse(
		score=72.5,
		risk_level="high",
		generated_at=datetime.now(timezone.utc).isoformat(),
		metadata={"source": "bootstrap-endpoint"},
	)

