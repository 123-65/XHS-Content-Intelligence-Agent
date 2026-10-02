"""基于现有正式 Repository 的只读 identity adapter。"""

from app.agent.context.contracts import IdentityRecord, ObjectRef, ResolvedObjectType
from app.repositories.content_strategy_repo import ContentStrategyRepository
from app.repositories.draft_repo import DraftRepository
from app.repositories.publication_repo import PublicationRepository
from app.repositories.workflow_run_repo import WorkflowRunRepository


class RepositoryContextIdentityReader:
    """只调用 canonical read API；不 commit、不创建业务对象。"""

    def __init__(self, db):
        self.strategies = ContentStrategyRepository(db)
        self.drafts = DraftRepository(db)
        self.publications = PublicationRepository(db)
        self.runs = WorkflowRunRepository(db)

    def get_identity(self, ref: ObjectRef) -> IdentityRecord | None:
        if ref.type == ResolvedObjectType.CONTENT_OPPORTUNITY:
            return self._opportunity_identity(ref)
        getters = {
            ResolvedObjectType.ACCOUNT: self.strategies.get_account,
            ResolvedObjectType.RESEARCH: self.strategies.get_report,
            ResolvedObjectType.CONTENT_STRATEGY: self.strategies.get_strategy_artifact,
            ResolvedObjectType.DRAFT: self.drafts.get_draft,
            ResolvedObjectType.PUBLISHED_NOTE: self.publications.get_note,
            ResolvedObjectType.RUN: self.runs.get_by_run_ref,
        }
        item = getters[ref.type](ref.id)
        if item is None:
            return None
        account_ref = item.id if ref.type == ResolvedObjectType.ACCOUNT else item.account_id
        return IdentityRecord(
            ref=ref,
            account_ref=account_ref,
            published_at=getattr(item, "published_at", None),
            external_identity=(getattr(item, "platform_account_id", None) if ref.type == ResolvedObjectType.ACCOUNT else None),
        )

    def _opportunity_identity(self, ref: ObjectRef) -> IdentityRecord | None:
        """Resolve Opportunity ownership through its explicit canonical domain relation."""
        opportunity = self.strategies.get_opportunity(ref.id)
        if opportunity is None:
            return None
        if opportunity.strategy_artifact_id is not None:
            owner = self.strategies.get_strategy_artifact(opportunity.strategy_artifact_id)
        else:
            owner = self.strategies.get_report(opportunity.report_id)
        if owner is None or owner.account_id is None:
            return None
        return IdentityRecord(ref=ref, account_ref=owner.account_id)

    def list_published_between(self, account_ref, start, end):
        return [
            IdentityRecord(
                ref=ObjectRef(type=ResolvedObjectType.PUBLISHED_NOTE, id=item.id),
                account_ref=item.account_id,
                published_at=item.published_at,
            )
            for item in self.publications.list_notes_published_between(account_ref, start, end)
        ]

    def latest_published(self, account_ref):
        item = self.publications.get_latest_published_note(account_ref)
        if item is None:
            return None
        return IdentityRecord(
            ref=ObjectRef(type=ResolvedObjectType.PUBLISHED_NOTE, id=item.id),
            account_ref=item.account_id,
            published_at=item.published_at,
        )
