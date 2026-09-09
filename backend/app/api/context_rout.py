from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, selectinload

from app.context.context_snapshot import TracePayloadGovernor
from app.core.database import get_db
from app.core.response import fail, success
from app.models.context_snapshot import ContextSnapshot
from app.schemas.context import ContextSnapshotResponse, TraceRetentionPolicyResponse

router = APIRouter(tags=["context-trace"])


def _not_found(message: str) -> JSONResponse:
    return JSONResponse(status_code=404, content=fail(code=404, message=message).model_dump())


@router.get("/api/context/snapshots/{snapshot_id}")
def get_context_snapshot(snapshot_id: int, db: Session = Depends(get_db)):
    """Return one context snapshot with slot logs."""
    snapshot = (
        db.query(ContextSnapshot)
        .options(selectinload(ContextSnapshot.slot_logs))
        .filter(ContextSnapshot.id == snapshot_id)
        .one_or_none()
    )
    if not snapshot:
        return _not_found("Context snapshot does not exist")
    return success(ContextSnapshotResponse.model_validate(snapshot).model_dump(mode="json"))


@router.get("/api/trace/retention-policy")
def get_trace_retention_policy():
    """Return default trace retention policies."""
    policies = [TraceRetentionPolicyResponse.model_validate(item).model_dump() for item in TracePayloadGovernor().policies_as_dicts()]
    return success(policies)

