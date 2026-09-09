from sqlalchemy import select
from sqlalchemy.orm import Session

from app.context.context_snapshot import TracePayloadGovernor
from app.models.account import AccountProfile
from app.models.content_draft import ContentDraft
from app.models.content_draft_version import ContentDraftVersion
from app.models.content_experiment import ContentExperiment
from app.models.content_opportunity import ContentOpportunity
from app.models.draft_generation_context import DraftGenerationContext
from app.models.prompt_run_log import PromptRunLog
from app.schemas.content_draft_v2 import (
    ContentDraftV2Create,
    ContentDraftVersionCreate,
    DraftGenerationContextCreate,
    PromptRunLogCreate,
)


class ContentDraftV2Repository:
    """Database access layer for V2 draft generation."""

    def __init__(self, db: Session):
        """Initialize the repository."""
        self.db = db
        self.trace_governor = TracePayloadGovernor()

    def get_account(self, account_id: int) -> AccountProfile | None:
        """Get an account profile by ID."""
        return self.db.get(AccountProfile, account_id)

    def get_experiment(self, experiment_id: int) -> ContentExperiment | None:
        """Get a content experiment by ID."""
        return self.db.get(ContentExperiment, experiment_id)

    def get_opportunity(self, opportunity_id: int | None) -> ContentOpportunity | None:
        """Get a content opportunity by ID."""
        return self.db.get(ContentOpportunity, opportunity_id) if opportunity_id else None

    def get_draft(self, draft_id: int) -> ContentDraft | None:
        """Get a content draft by ID."""
        return self.db.get(ContentDraft, draft_id)

    def create_prompt_run_log(self, data: PromptRunLogCreate) -> PromptRunLog:
        """Create a prompt run log."""
        fields = data.model_dump()
        fields["input_payload"] = self.trace_governor.govern_payload(fields.get("input_payload", {}), "prompt_run_log")
        fields["input_summary"] = self.trace_governor.govern_payload(fields.get("input_summary", {}), "prompt_run_log")
        fields["rendered_prompt"] = self.trace_governor.govern_text(fields.get("rendered_prompt"), "prompt_run_log") or ""
        fields["output_text"] = self.trace_governor.govern_text(fields.get("output_text"), "prompt_run_log")
        fields["output_json"] = self.trace_governor.govern_payload(fields.get("output_json", {}), "prompt_run_log")
        fields["output_summary"] = self.trace_governor.govern_payload(fields.get("output_summary", {}), "prompt_run_log")
        fields["error_message"] = self.trace_governor.govern_text(fields.get("error_message"), "prompt_run_log")
        log = PromptRunLog(**fields)
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def create_generation_context(self, data: DraftGenerationContextCreate) -> DraftGenerationContext:
        """Create a draft generation context."""
        context = DraftGenerationContext(**data.model_dump())
        self.db.add(context)
        self.db.commit()
        self.db.refresh(context)
        return context

    def create_draft(self, data: ContentDraftV2Create) -> ContentDraft:
        """Create a content draft."""
        draft = ContentDraft(**data.model_dump())
        self.db.add(draft)
        self.db.commit()
        self.db.refresh(draft)
        return draft

    def update_context_draft(self, context: DraftGenerationContext, draft_id: int) -> DraftGenerationContext:
        """Backfill the draft ID onto a generation context."""
        context.draft_id = draft_id
        self.db.commit()
        self.db.refresh(context)
        return context

    def create_version(self, data: ContentDraftVersionCreate) -> ContentDraftVersion:
        """Create a draft version snapshot."""
        version = ContentDraftVersion(**data.model_dump())
        self.db.add(version)
        self.db.commit()
        self.db.refresh(version)
        return version

    def list_versions(self, draft_id: int) -> list[ContentDraftVersion]:
        """List draft versions newest first."""
        stmt = (
            select(ContentDraftVersion)
            .where(ContentDraftVersion.draft_id == draft_id)
            .order_by(ContentDraftVersion.version.desc(), ContentDraftVersion.id.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_generation_context(self, draft_id: int) -> DraftGenerationContext | None:
        """Get the latest generation context for a draft."""
        stmt = (
            select(DraftGenerationContext)
            .where(DraftGenerationContext.draft_id == draft_id)
            .order_by(DraftGenerationContext.id.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def update_draft(self, draft: ContentDraft, fields: dict) -> ContentDraft:
        """Update fields on a content draft."""
        for key, value in fields.items():
            setattr(draft, key, value)
        self.db.commit()
        self.db.refresh(draft)
        return draft

    def update_experiment_status(self, experiment: ContentExperiment, status: str) -> None:
        """Update experiment status."""
        experiment.status = status
        self.db.commit()
