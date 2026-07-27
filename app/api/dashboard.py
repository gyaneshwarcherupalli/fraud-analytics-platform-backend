"""Dashboard and KPI endpoints."""
from fastapi import APIRouter


router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/metrics", summary="Get dashboard metrics")
async def get_dashboard_metrics():
	"""Return top-level dashboard KPI placeholders."""
	return {
		"transactions_processed": 0,
		"fraud_detected": 0,
		"alerts_generated": 0,
		"average_risk_score": 0.0,
	}

