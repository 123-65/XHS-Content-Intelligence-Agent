import pytest

from app.agent.control.current_turn_materials import (
    CurrentMaterialSource,
    CurrentMaterialType,
    NormalizedCurrentMaterial,
)
from app.agent.conversation_v2.decision_context import (
    CanonicalTurnContextBuilder,
    PendingFact,
)
from app.agent.conversation_v2.workspace import RecentTrustedContext, TrustedWorkspaceSnapshot
from app.agent.workflows.definitions import WorkflowId


PROFILE = "https://www.xiaohongshu.com/user/profile/u1?xsec_token=keep"
NOTE = "https://www.xiaohongshu.com/explore/n1?xsec_token=keep"


def material(material_type, url=PROFILE, source=CurrentMaterialSource.EXPLICIT_MATERIAL):
    return NormalizedCurrentMaterial(material_type=material_type, source_url=url, source=source)


def context(*, materials=(), workspace=None, recent=None, pending=None):
    return CanonicalTurnContextBuilder().build(
        current_materials=tuple(materials),
        workspace=workspace or TrustedWorkspaceSnapshot(),
        recent=recent or RecentTrustedContext(),
        pending=pending,
    )


def test_business_action_without_material_keeps_research_bootstrap_candidate():
    assert context().candidate_tools == ("run_research",)


@pytest.mark.parametrize(
    "materials",
    [
        (material(CurrentMaterialType.EXTERNAL_XHS_PROFILE),),
        (material(CurrentMaterialType.EXTERNAL_XHS_NOTE, NOTE),),
        tuple(
            material(CurrentMaterialType.EXTERNAL_XHS_PROFILE, PROFILE.replace("u1", f"u{index}"))
            for index in range(1, 4)
        ),
    ],
)
def test_current_external_materials_only_expose_consuming_tool(materials):
    assert context(materials=materials).candidate_tools == ("run_research",)


def test_research_artifact_makes_strategy_eligible_without_forcing_it():
    assert context(workspace=TrustedWorkspaceSnapshot(research_ref=11)).candidate_tools == (
        "run_research",
        "run_content_strategy",
    )


def test_opportunity_with_verified_strategy_lineage_makes_creation_eligible():
    assert context(workspace=TrustedWorkspaceSnapshot(
        opportunity_ref=12,
        opportunity_strategy_ref=13,
    )).candidate_tools == ("run_research", "run_content_creation")


def test_draft_makes_refinement_eligible():
    assert context(workspace=TrustedWorkspaceSnapshot(draft_ref=14)).candidate_tools == (
        "run_research",
        "run_content_refinement",
    )


def test_published_note_makes_post_publish_review_eligible():
    assert context(workspace=TrustedWorkspaceSnapshot(published_note_ref=15)).candidate_tools == (
        "run_research",
        "run_post_publish_review",
    )


def test_external_note_is_not_a_published_note_candidate():
    value = context(materials=(material(CurrentMaterialType.EXTERNAL_XHS_NOTE, NOTE),))
    assert value.candidate_tools == ("run_research",)
    assert "run_post_publish_review" not in value.candidate_tools


def test_satisfied_pending_research_is_singleton_candidate():
    pending = PendingFact(
        workflow_type=WorkflowId.RESEARCH_V1,
        required_fields=("research_material",),
        resumable=True,
        requirements_satisfied=True,
    )
    value = context(
        materials=(material(CurrentMaterialType.EXTERNAL_XHS_PROFILE),),
        workspace=TrustedWorkspaceSnapshot(published_note_ref=15),
        pending=pending,
    )
    assert value.candidate_tools == ("run_research",)


def test_current_material_authority_hides_stale_recent_candidates():
    value = context(
        materials=(material(CurrentMaterialType.EXTERNAL_XHS_PROFILE),),
        recent=RecentTrustedContext(strategy_ref=21, draft_ref=22),
    )
    assert value.candidate_tools == ("run_research",)


def test_opportunity_without_verified_strategy_lineage_is_not_creation_eligible():
    value = context(workspace=TrustedWorkspaceSnapshot(opportunity_ref=12))
    assert value.candidate_tools == ("run_research",)


def test_model_visible_projection_contains_safe_counts_not_raw_urls():
    value = context(materials=(
        material(CurrentMaterialType.EXTERNAL_XHS_PROFILE, PROFILE),
        material(CurrentMaterialType.EXTERNAL_XHS_PROFILE, PROFILE.replace("u1", "u2")),
        material(CurrentMaterialType.EXTERNAL_XHS_PROFILE, PROFILE.replace("u1", "u3")),
    ))
    prompt = value.prompt_text()
    assert "EXTERNAL_XHS_PROFILE" in prompt
    assert "'count': 3" in prompt
    assert "EXPLICIT_MATERIAL" in prompt
    assert "xiaohongshu.com" not in prompt
