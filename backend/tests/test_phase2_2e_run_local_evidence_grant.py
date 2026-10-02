from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.agent.schemas.evidence import EvidenceRef, EvidenceType
from app.agent.tools.access_scopes import EvidenceAccessScope, RunLocalEvidenceGrant
from app.agent.tools.definitions import ToolError, ToolResult
from app.agent.tools.query_contracts import RetrieveResearchEvidenceInput
from app.agent.tools.query_tools import RetrieveResearchEvidenceTool
from app.agent.tools.xhs_contracts import (
    CollectionAuthorizationSource,
    CollectXhsNotesResult,
    CollectedNoteResult,
    FailedCollectionItem,
    NoteCollectionPurpose,
)


TOOLS_ROOT = Path(__file__).resolve().parents[1] / "app" / "agent" / "tools"
REF_A = EvidenceRef(type=EvidenceType.NOTE, id=1)
REF_B = EvidenceRef(type=EvidenceType.NOTE, id=2)
REF_C = EvidenceRef(type=EvidenceType.NOTE, id=3)


def _success_result(*refs, failed=False):
    items = [
        CollectedNoteResult(
            source_url=f"https://www.xiaohongshu.com/explore/{ref.id}",
            note_ref=ref.id,
            evidence_refs=[ref],
            collected_at=datetime.now(timezone.utc),
            authorized_by=CollectionAuthorizationSource.USER_PROVIDED,
            collection_purpose=NoteCollectionPurpose.RESEARCH_INPUT,
            comments_collected=0,
        )
        for ref in refs
    ]
    failed_items = (
        [FailedCollectionItem(source_url="https://www.xiaohongshu.com/explore/failed", error_code="PROVIDER_ERROR")]
        if failed
        else []
    )
    return ToolResult(
        success=True,
        data=CollectXhsNotesResult(
            requested_count=len(items) + len(failed_items),
            collected_count=len(items),
            failed_count=len(failed_items),
            items=items,
            failed_items=failed_items,
            warnings=["PARTIAL_XHS_COLLECTION"] if failed else [],
        ),
    )


def test_external_scope_is_preserved_when_run_local_refs_are_added():
    existing = EvidenceAccessScope(authorized_refs=frozenset({REF_A}))
    grant = RunLocalEvidenceGrant.from_successful_collection_result(_success_result(REF_B, REF_C))

    effective = existing.with_run_local_grant(grant)

    assert effective.authorized_refs == frozenset({REF_A, REF_B, REF_C})
    assert existing.authorized_refs == frozenset({REF_A})
    assert effective is not existing


def test_run_local_grant_can_create_scope_without_historical_scope():
    grant = RunLocalEvidenceGrant.from_successful_collection_result(_success_result(REF_B))

    effective = EvidenceAccessScope.from_run_local_grant(grant)

    assert effective.authorized_refs == frozenset({REF_B})


def test_partial_collection_grants_only_successful_item_refs():
    grant = RunLocalEvidenceGrant.from_successful_collection_result(
        _success_result(REF_B, failed=True)
    )

    assert grant.trusted_collected_refs == frozenset({REF_B})
    assert REF_C not in grant.trusted_collected_refs


def test_failed_collection_and_raw_user_refs_cannot_create_grant():
    failed = ToolResult(
        success=False,
        error=ToolError(
            code="PROVIDER_ERROR",
            category="PROVIDER",
            retryable=True,
            safe_message="采集失败",
        ),
    )

    with pytest.raises(ValueError, match="失败"):
        RunLocalEvidenceGrant.from_successful_collection_result(failed)
    with pytest.raises(TypeError, match="只能由成功 Collection"):
        RunLocalEvidenceGrant(frozenset({REF_C}), _token=object())
    with pytest.raises(TypeError, match="RunLocalEvidenceGrant"):
        EvidenceAccessScope.deny_all().with_run_local_grant([REF_C])


class FakeEvidenceFacade:
    def get_evidence(self, account_ref, evidence_ref):
        return None


def test_retrieval_still_rejects_ref_outside_effective_scope():
    grant = RunLocalEvidenceGrant.from_successful_collection_result(_success_result(REF_B))
    effective = EvidenceAccessScope.from_run_local_grant(grant)
    tool = RetrieveResearchEvidenceTool(facade=FakeEvidenceFacade(), access_scope=effective)

    result = tool.execute(
        RetrieveResearchEvidenceInput(
            account_ref=7,
            evidence_refs=[REF_C],
            purpose="研究",
        )
    )

    assert not result.success
    assert result.error.code == "VALIDATION_ERROR"


def test_grant_helper_has_no_infrastructure_or_untrusted_input_dependency():
    source = (TOOLS_ROOT / "access_scopes.py").read_text(encoding="utf-8")
    forbidden = (
        "sqlalchemy",
        "app.repositories",
        "Provider",
        "fastapi",
        "HTTPException",
        "app.llm",
        "ResearchWorkflowInput",
        "note_urls",
        "profile_urls",
        "artifact_refs",
    )
    assert not [token for token in forbidden if token in source]
