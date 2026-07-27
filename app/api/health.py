"""Health-related API endpoints."""
from datetime import datetime, timezone

from fastapi import APIRouter


router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("", summary="Service health status")
async def get_service_health():
	"""Return lightweight service health information."""
	return {
		"status": "ok",
		"service": "fraud-analytics-backend",
		"timestamp": datetime.now(timezone.utc).isoformat(),
	}
