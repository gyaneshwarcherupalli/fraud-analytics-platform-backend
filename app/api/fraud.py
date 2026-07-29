"""Fraud scoring and risk endpoints."""
from math import ceil
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.fraud_repository import FraudRepository
from app.repositories.transaction_repository import TransactionRepository
from app.schemas.fraud_schema import (
    FraudScoreBatchRequest,
    FraudScoreBatchResponse,
    FraudScoreListResponse,
    FraudScoreRecord,
    FraudScoreRequest,
    FraudScoreResult,
)
from app.services.fraud_engine.fraud_scoring import FraudScoringEngine
from app.utils.exceptions import FraudAnalyticsException


router = APIRouter(prefix="/api/fraud", tags=["fraud"])

# Module-level engine instance; loaded lazily on first use.
_engine: Optional[FraudScoringEngine] = None


def _get_engine() -> FraudScoringEngine:
    global _engine
    if _engine is None:
        _engine = FraudScoringEngine()
        try:
            _engine.load()
        except FraudAnalyticsException:
            # Model artifacts not present; engine will operate in degraded mode
            pass
    return _engine


# ---------------------------------------------------------------------------
# Scoring endpoints
# ---------------------------------------------------------------------------

@router.post("/score", response_model=FraudScoreResult, summary="Score a single transaction")
async def score_transaction(
    payload: FraudScoreRequest,
    persist: bool = Query(default=False, description="Persist score to DB when transaction_ref resolves to a known record"),
    db: Session = Depends(get_db),
) -> FraudScoreResult:
    """Run the fraud scoring engine against a single transaction payload.

    If *persist* is ``true`` and *transaction_ref* resolves to an existing
    transaction row the score is saved to the ``fraud_scores`` table.
    """
    engine = _get_engine()
    raw = payload.model_dump(exclude_none=True)

    try:
        result = engine.score_transaction(raw)
    except FraudAnalyticsException as exc:
        raise HTTPException(status_code=503, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if persist and payload.transaction_ref:
        tx_repo = TransactionRepository(db)
        score_repo = FraudRepository(db)
        tx = tx_repo.get_by_ref(payload.transaction_ref)
        if tx is not None:
            try:
                score_repo.create_fraud_score(tx.id, result)
                db.commit()
            except Exception:
                db.rollback()

    return FraudScoreResult(**result)


@router.post("/score/batch", response_model=FraudScoreBatchResponse, summary="Score multiple transactions")
async def score_transactions_batch(
    payload: FraudScoreBatchRequest,
    persist: bool = Query(default=False, description="Persist scores for resolved transaction refs"),
    db: Session = Depends(get_db),
) -> FraudScoreBatchResponse:
    """Score up to 500 transactions in a single request."""
    engine = _get_engine()
    raw_payloads = [t.model_dump(exclude_none=True) for t in payload.transactions]

    try:
        batch_result = engine.score_batch(raw_payloads, skip_errors=payload.skip_errors)
    except FraudAnalyticsException as exc:
        raise HTTPException(status_code=503, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if persist:
        tx_repo = TransactionRepository(db)
        score_repo = FraudRepository(db)
        for scored in batch_result["results"]:
            ref = scored.get("transaction_ref")
            if ref:
                tx = tx_repo.get_by_ref(ref)
                if tx is not None:
                    score_repo.create_fraud_score(tx.id, scored)
        try:
            db.commit()
        except Exception:
            db.rollback()

    return FraudScoreBatchResponse(
        results=[FraudScoreResult(**r) for r in batch_result["results"]],
        errors=batch_result["errors"],
        summary=batch_result["summary"],
    )


# ---------------------------------------------------------------------------
# Fraud score record endpoints
# ---------------------------------------------------------------------------

@router.get("/scores", response_model=FraudScoreListResponse, summary="List fraud score records")
async def list_fraud_scores(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    risk_level: Optional[str] = Query(default=None, description="Filter by risk level (LOW/MEDIUM/HIGH/CRITICAL)"),
    is_fraud_predicted: Optional[bool] = Query(default=None),
    db: Session = Depends(get_db),
) -> FraudScoreListResponse:
    """Return a paginated list of persisted fraud score records."""
    repo = FraudRepository(db)
    items, total = repo.list_fraud_scores(
        page=page,
        page_size=page_size,
        risk_level=risk_level,
        is_fraud_predicted=is_fraud_predicted,
    )
    return FraudScoreListResponse(
        items=[FraudScoreRecord.model_validate(s) for s in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=ceil(total / page_size) if page_size else 1,
    )


@router.get("/scores/transaction/{transaction_id}", response_model=FraudScoreListResponse, summary="Get scores for a transaction")
async def get_scores_for_transaction(
    transaction_id: UUID,
    db: Session = Depends(get_db),
) -> FraudScoreListResponse:
    """Return all fraud scores linked to a transaction, newest first."""
    repo = FraudRepository(db)
    items = repo.list_for_transaction(transaction_id)
    return FraudScoreListResponse(
        items=[FraudScoreRecord.model_validate(s) for s in items],
        total=len(items),
        page=1,
        page_size=len(items) or 1,
        pages=1,
    )


@router.get("/scores/{score_id}", response_model=FraudScoreRecord, summary="Get fraud score by ID")
async def get_fraud_score(
    score_id: UUID,
    db: Session = Depends(get_db),
) -> FraudScoreRecord:
    """Return a single persisted fraud score record by its UUID."""
    repo = FraudRepository(db)
    instance = repo.get_by_id(score_id)
    if instance is None:
        raise HTTPException(status_code=404, detail="Fraud score not found")
    return FraudScoreRecord.model_validate(instance)

