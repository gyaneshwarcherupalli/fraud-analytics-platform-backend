"""Investigation workflow endpoints."""
from fastapi import APIRouter


router = APIRouter(prefix="/api/investigations", tags=["investigations"])


@router.get("/queue", summary="Get investigation queue")
async def get_investigation_queue():
	"""Return the current investigation queue snapshot."""
	return {
		"pending": 0,
		"in_progress": 0,
		"completed_today": 0,
	}

