from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.post_publish_review_v0 import PostPublishReviewV0Request, PostPublishReviewV0Response
from app.services.post_publish_review_v0_sev import PostPublishReviewV0NotFound, PostPublishReviewV0Service

router = APIRouter(prefix="/agent", tags=["agent-post-publish-review-v0"])


@router.post("/published-notes/{published_note_id}/post-publish-reviews", response_model=PostPublishReviewV0Response)
def create_post_publish_review(
    published_note_id: int,
    data: PostPublishReviewV0Request,
    db: Session = Depends(get_db),
) -> PostPublishReviewV0Response:
    try:
        return PostPublishReviewV0Service(db).create_review(published_note_id, data)
    except PostPublishReviewV0NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/published-notes/{published_note_id}/post-publish-reviews", response_model=list[PostPublishReviewV0Response])
def list_post_publish_reviews(
    published_note_id: int,
    db: Session = Depends(get_db),
) -> list[PostPublishReviewV0Response]:
    try:
        return PostPublishReviewV0Service(db).list_by_published_note(published_note_id)
    except PostPublishReviewV0NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/post-publish-reviews/{review_id}", response_model=PostPublishReviewV0Response)
def get_post_publish_review(
    review_id: int,
    db: Session = Depends(get_db),
) -> PostPublishReviewV0Response:
    try:
        return PostPublishReviewV0Service(db).get_review(review_id)
    except PostPublishReviewV0NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
