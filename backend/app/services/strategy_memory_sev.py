from sqlalchemy.orm import Session

from app.repositories.publication_repo import PublicationRepository
from app.schemas.publication import ConfirmStrategyCandidateInput, StrategyMemoryResult


class StrategyMemoryService:
    """仅将用户明确确认的策略候选保存为长期记忆。"""

    def __init__(self, db: Session, repository: PublicationRepository | None = None):
        """初始化策略记忆持久化服务；该服务不使用大模型。"""
        self.repo = repository or PublicationRepository(db)

    def confirm_candidate(self, data: ConfirmStrategyCandidateInput) -> StrategyMemoryResult:
        """经显式确认门禁后保存指定候选；未确认时不写库。"""
        report = self.repo.get_review(data.review_ref)
        if not report or report.account_id != data.account_id or report.review_type != "POST_PUBLISH_REVIEW_V1":
            raise ValueError("PostPublishReview 不存在或不属于当前账号")
        candidates = report.action_suggestions or []
        candidate = next((item for item in candidates if item.get("candidate_index") == data.candidate_index), None)
        if not candidate:
            raise ValueError("Strategy Candidate 不存在")
        if not data.confirmed:
            return StrategyMemoryResult(status="WAITING_CONFIRMATION")
        memory = self.repo.create_memory(data.account_id, report.id, {**candidate, "status": "CONFIRMED"})
        return StrategyMemoryResult(status="SAVED", memory_ref=memory.id)
