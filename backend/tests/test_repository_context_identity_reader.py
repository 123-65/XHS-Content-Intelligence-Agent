import pytest

from app.agent.context.contracts import ObjectRef, ResolvedObjectType
from app.agent.context.repository_reader import RepositoryContextIdentityReader
from app.core.database import SessionLocal
from app.models.account import AccountProfile
from app.models.competitors_analysis import CompetitorAnalysisReport
from app.models.content_draft import ContentDraft
from app.models.content_opportunity import ContentOpportunity
from app.models.content_strategy_artifact import ContentStrategyArtifact
from app.schemas.unified_agent import AgentTurnRequest
from app.services.unified_agent_sev import UnifiedAgentError, UnifiedAgentService


def _ref(kind, identity):
    return ObjectRef(type=kind, id=identity)


def _opportunity(report_id, **overrides):
    values = {
        "report_id": report_id,
        "opportunity_title": "真实机会",
        "suggested_angle": "真实角度",
        "content_pillar": "测试",
        "comment_demand_type": "QUESTION",
        "evidence_summary": "真实证据",
        "opportunity_score": 80,
    }
    values.update(overrides)
    return ContentOpportunity(**values)


def _request(account_ref, opportunity_ref):
    return AgentTurnRequest(
        conversation_id=1,
        account_ref=account_ref,
        text="用这个写一篇",
        workspace_selection={"opportunity_ref": opportunity_ref},
        client_request_id=f"identity-{account_ref}-{opportunity_ref}",
    )


def test_opportunity_identity_uses_explicit_strategy_or_research_owner_and_preserves_other_types():
    with SessionLocal() as db:
        try:
            account = AccountProfile(account_name="Identity A", positioning="test", target_audience="test")
            db.add(account); db.flush()
            report = CompetitorAnalysisReport(account_id=account.id, name="Research", summary="test")
            db.add(report); db.flush()
            historical = _opportunity(report.id)
            db.add(historical); db.flush()
            strategy = ContentStrategyArtifact(
                account_id=account.id, research_artifact_id=report.id, strategy_goal="goal",
                target_audience="audience", content_directions=[], rationale="reason",
                evidence_refs=[], applicable_constraints=[], provider="test", model="test",
            )
            db.add(strategy); db.flush()
            generated = _opportunity(
                report.id, strategy_artifact_id=strategy.id, source_opportunity_id=historical.id,
                content_goal="goal", why_now="now", suggested_hook="hook", evidence_refs=[], constraints=[],
            )
            db.add(generated); db.flush()
            draft = ContentDraft(
                account_id=account.id, strategy_artifact_id=strategy.id, opportunity_id=generated.id,
                content_goal="goal", title="title", body="body", tags=[], version=1,
            )
            db.add(draft); db.flush()

            reader = RepositoryContextIdentityReader(db)
            assert reader.get_identity(_ref(ResolvedObjectType.CONTENT_OPPORTUNITY, generated.id)).account_ref == account.id
            assert reader.get_identity(_ref(ResolvedObjectType.CONTENT_OPPORTUNITY, historical.id)).account_ref == account.id
            assert reader.get_identity(_ref(ResolvedObjectType.CONTENT_OPPORTUNITY, 999_999_999)) is None
            assert reader.get_identity(_ref(ResolvedObjectType.RESEARCH, report.id)).account_ref == account.id
            assert reader.get_identity(_ref(ResolvedObjectType.CONTENT_STRATEGY, strategy.id)).account_ref == account.id
            assert reader.get_identity(_ref(ResolvedObjectType.DRAFT, draft.id)).account_ref == account.id
        finally:
            db.rollback()


def test_workspace_selection_accepts_canonical_owner_and_rejects_client_account_for_both_opportunity_types():
    with SessionLocal() as db:
        try:
            account_a = AccountProfile(account_name="Workspace A", positioning="test", target_audience="test")
            account_b = AccountProfile(account_name="Workspace B", positioning="test", target_audience="test")
            db.add_all([account_a, account_b]); db.flush()
            report = CompetitorAnalysisReport(account_id=account_a.id, name="Research", summary="test")
            db.add(report); db.flush()
            historical = _opportunity(report.id)
            db.add(historical); db.flush()
            strategy = ContentStrategyArtifact(
                account_id=account_a.id, research_artifact_id=report.id, strategy_goal="goal",
                target_audience="audience", content_directions=[], rationale="reason",
                evidence_refs=[], applicable_constraints=[], provider="test", model="test",
            )
            db.add(strategy); db.flush()
            generated = _opportunity(
                report.id, strategy_artifact_id=strategy.id, source_opportunity_id=historical.id,
                content_goal="goal", why_now="now", suggested_hook="hook", evidence_refs=[], constraints=[],
            )
            db.add(generated); db.flush()

            service = UnifiedAgentService(db)
            workspace = service._workspace(_request(account_a.id, generated.id))
            assert workspace.references[0].ref == _ref(ResolvedObjectType.CONTENT_OPPORTUNITY, generated.id)
            assert workspace.references[0].account_ref == account_a.id

            for opportunity in (generated, historical):
                with pytest.raises(UnifiedAgentError, match="不属于当前 Account") as rejected:
                    service._workspace(_request(account_b.id, opportunity.id))
                assert rejected.value.code == "WORKSPACE_ACCOUNT_MISMATCH"

            with pytest.raises(UnifiedAgentError, match="不存在") as missing:
                service._workspace(_request(account_a.id, 999_999_999))
            assert missing.value.code == "WORKSPACE_REFERENCE_NOT_FOUND"
        finally:
            db.rollback()
