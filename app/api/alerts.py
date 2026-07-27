"""Alert management endpoints."""
from fastapi import APIRouter


router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("/summary", summary="Get alert summary")
async def get_alert_summary():
	"""Return placeholder alert summary counts."""
	return {
		"open_alerts": 0,
		"closed_alerts": 0,
		"high_priority_alerts": 0,
	}

