"""Investigation workflow endpoints."""
from math import ceil
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.investigation_repository import InvestigationRepository
from app.schemas.investigation_schema import (
    InvestigationCreate,
    InvestigationListResponse,
    InvestigationQueueResponse,
    InvestigationResponse,
    InvestigationUpdate,
)
from app.utils.exceptions import DatabaseException, DataNotFoundError


router = APIRouter(prefix="/api/investigations", tags=["investigations"])


@router.get("/queue", response_model=InvestigationQueueResponse, summary="Get investigation queue")
def get_investigation_queue(db: Session = Depends(get_db)) -> InvestigationQueueResponse:
    """Return live investigation workload counts."""
    return InvestigationQueueResponse(**InvestigationRepository(db).queue_summary())


@router.post("", response_model=InvestigationResponse, status_code=201, summary="Create investigation")
def create_investigation(
    payload: InvestigationCreate,
    db: Session = Depends(get_db),
) -> InvestigationResponse:
    """Create an investigation for an existing alert."""
    try:
        investigation = InvestigationRepository(db).create(payload)
        db.commit()
        db.refresh(investigation)
    except DataNotFoundError:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise DatabaseException("Unable to create investigation") from exc
    return InvestigationResponse.model_validate(investigation)


@router.get("", response_model=InvestigationListResponse, summary="List investigations")
def list_investigations(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    investigator: Optional[str] = Query(None),
    alert_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
) -> InvestigationListResponse:
    """Return a filtered, paginated investigation list."""
    items, total = InvestigationRepository(db).list_investigations(
        page=page, page_size=page_size, status=status, priority=priority,
        investigator=investigator, alert_id=alert_id,
    )
    return InvestigationListResponse(
        items=[InvestigationResponse.model_validate(item) for item in items],
        total=total, page=page, page_size=page_size,
        pages=ceil(total / page_size),
    )


@router.get("/{investigation_id}", response_model=InvestigationResponse, summary="Get investigation")
def get_investigation(
    investigation_id: UUID,
    db: Session = Depends(get_db),
) -> InvestigationResponse:
    """Return an investigation by ID."""
    investigation = InvestigationRepository(db).get_by_id(investigation_id)
    if investigation is None:
        raise DataNotFoundError("Investigation not found")
    return InvestigationResponse.model_validate(investigation)


@router.patch("/{investigation_id}", response_model=InvestigationResponse, summary="Update investigation")
def update_investigation(
    investigation_id: UUID,
    payload: InvestigationUpdate,
    db: Session = Depends(get_db),
) -> InvestigationResponse:
    """Assign, prioritize, progress, or close an investigation."""
    repository = InvestigationRepository(db)
    investigation = repository.get_by_id(investigation_id)
    if investigation is None:
        raise DataNotFoundError("Investigation not found")
    try:
        investigation = repository.update(investigation, payload)
        db.commit()
        db.refresh(investigation)
    except SQLAlchemyError as exc:
        db.rollback()
        raise DatabaseException("Unable to update investigation") from exc
    return InvestigationResponse.model_validate(investigation)

