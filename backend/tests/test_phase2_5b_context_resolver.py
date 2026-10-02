from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.agent.context.contracts import (
    ContextResolverInput, CurrentTurnMaterialCandidate, CurrentTurnMaterialType, IdentityRecord, ObjectRef, OpportunityCollection,
    ResolvedObjectType, StructuredContext, TrustedContextRef,
)
from app.agent.context.resolver import ContextResolver
from app.agent.control.semantic_layer import ControlAgentSemanticLayer
from app.agent.schemas.semantic import Intent, SemanticReference, SemanticReferenceType, TaskSemanticFrame


ACCOUNT = 7
NOW = datetime(2026, 9, 22, 12, tzinfo=UTC)


class FakeIdentityReader:
    def __init__(self, records=()):
        self.records = {record.ref: record for record in records}
        self.reads = []
        self.writes = 0
        self.llm_calls = 0

    def get_identity(self, ref):
        self.reads.append(("get", ref))
        return self.records.get(ref)

    def list_published_between(self, account_ref, start, end):
        self.reads.append(("between", account_ref, start, end))
        return [r for r in self.records.values() if r.ref.type == ResolvedObjectType.PUBLISHED_NOTE and r.account_ref == account_ref and r.published_at and start <= r.published_at < end]

    def latest_published(self, account_ref):
        self.reads.append(("latest", account_ref))
        items = [r for r in self.records.values() if r.ref.type == ResolvedObjectType.PUBLISHED_NOTE and r.account_ref == account_ref and r.published_at]
        return max(items, key=lambda item: (item.published_at, str(item.ref.id)), default=None)


def ref(kind, identity, account=ACCOUNT):
    value = ObjectRef(type=kind, id=identity)
    return TrustedContextRef(ref=value, account_ref=account)


def record(item, published_at=None):
    return IdentityRecord(ref=item.ref, account_ref=item.account_ref, published_at=published_at)


def semantic(kind, raw, **kwargs):
    return SemanticReference(type=kind, raw_text=raw, **kwargs)


def request(reference, **kwargs):
    return ContextResolverInput(account_ref=ACCOUNT, semantic_frame=TaskSemanticFrame(primary_intent=Intent.CONTENT_REFINE, references=[reference], confidence=1), **kwargs)


def resolve(reader, data):
    return ContextResolver(reader, now=lambda: NOW).resolve(data)


def profile_material(identity="profile-1", account=ACCOUNT):
    return CurrentTurnMaterialCandidate(
        type=CurrentTurnMaterialType.PROFILE,
        account_ref=account,
        source_url=f"https://www.xiaohongshu.com/user/profile/{identity}?xsec_token=token",
        external_identity=identity,
    )


@pytest.mark.parametrize("raw", ["该账号", "这个账号"])
def test_research_profile_reference_is_satisfied_by_unique_current_turn_material(raw):
    frame = TaskSemanticFrame(
        primary_intent=Intent.RESEARCH,
        references=[semantic(SemanticReferenceType.PROFILE, raw)],
        profile_urls=[profile_material().source_url],
        confidence=1,
    )
    result = resolve(FakeIdentityReader(), ContextResolverInput(
        account_ref=ACCOUNT, semantic_frame=frame, current_turn_materials=[profile_material()],
    ))
    assert result.unresolved_references == []
    assert result.material_satisfied_references[0].external_identity == "profile-1"
    assert result.resolved_references == []


def test_research_deictic_it_is_satisfied_by_unique_profile_material():
    frame = TaskSemanticFrame(
        primary_intent=Intent.RESEARCH,
        references=[semantic(SemanticReferenceType.UNKNOWN, "它")],
        profile_urls=[profile_material().source_url],
        confidence=1,
    )
    result = resolve(FakeIdentityReader(), ContextResolverInput(
        account_ref=ACCOUNT, semantic_frame=frame, current_turn_materials=[profile_material()],
    ))
    assert result.material_satisfied_references and not result.blocking_missing_info


def test_multiple_current_turn_profiles_are_ambiguous():
    materials = [profile_material("profile-1"), profile_material("profile-2")]
    frame = TaskSemanticFrame(
        primary_intent=Intent.RESEARCH,
        references=[semantic(SemanticReferenceType.ACCOUNT, "该账号")],
        profile_urls=[item.source_url for item in materials],
        confidence=1,
    )
    result = resolve(FakeIdentityReader(), ContextResolverInput(
        account_ref=ACCOUNT, semantic_frame=frame, current_turn_materials=materials,
    ))
    assert result.material_satisfied_references == []
    assert result.ambiguous_references[0].candidate_materials == ["profile-1", "profile-2"]


def test_explicit_account_conflict_is_not_overridden_by_profile_material():
    explicit = ref(ResolvedObjectType.ACCOUNT, 11)
    identity = IdentityRecord(ref=explicit.ref, account_ref=ACCOUNT, external_identity="profile-a")
    frame = TaskSemanticFrame(
        primary_intent=Intent.RESEARCH,
        references=[semantic(SemanticReferenceType.PROFILE, "该账号")],
        profile_urls=[profile_material("profile-b").source_url], confidence=1,
    )
    result = resolve(FakeIdentityReader([identity]), ContextResolverInput(
        account_ref=ACCOUNT, semantic_frame=frame, explicit_references=[explicit],
        current_turn_materials=[profile_material("profile-b")],
    ))
    assert result.resolved_references == []
    assert result.ambiguous_references[0].reason == "EXPLICIT_MATERIAL_CONFLICT"


def test_current_turn_profile_material_precedes_workspace_account():
    workspace = ref(ResolvedObjectType.ACCOUNT, 11)
    frame = TaskSemanticFrame(
        primary_intent=Intent.RESEARCH,
        references=[semantic(SemanticReferenceType.PROFILE, "该账号")],
        profile_urls=[profile_material().source_url], confidence=1,
    )
    result = resolve(FakeIdentityReader([record(workspace)]), ContextResolverInput(
        account_ref=ACCOUNT, semantic_frame=frame,
        current_turn_materials=[profile_material()], workspace_selection=StructuredContext(references=[workspace]),
    ))
    assert result.material_satisfied_references
    assert result.resolved_references == []


def test_foreign_current_turn_profile_material_is_rejected():
    frame = TaskSemanticFrame(
        primary_intent=Intent.RESEARCH,
        references=[semantic(SemanticReferenceType.PROFILE, "该账号")], confidence=1,
    )
    result = resolve(FakeIdentityReader(), ContextResolverInput(
        account_ref=ACCOUNT, semantic_frame=frame, current_turn_materials=[profile_material(account=8)],
    ))
    assert result.unresolved_references[0].reason == "CONTEXT_ACCOUNT_MISMATCH"


class SemanticFakeLLM:
    def __init__(self, data):
        self.data = data
        self.calls = 0

    def generate_structured(self, **kwargs):
        self.calls += 1
        return SimpleNamespace(data=self.data)


def test_workspace_draft_has_priority_over_recent_draft():
    workspace, recent = ref(ResolvedObjectType.DRAFT, 100), ref(ResolvedObjectType.DRAFT, 200)
    reader = FakeIdentityReader([record(workspace), record(recent)])
    result = resolve(reader, request(semantic(SemanticReferenceType.ACTIVE_DRAFT, "这篇"), workspace_selection=StructuredContext(references=[workspace]), conversation_context=StructuredContext(references=[recent])))
    assert result.resolved_references[0].resolved_ref == workspace.ref
    assert result.resolved_references[0].resolution_source == "WORKSPACE_SELECTION"


def test_recent_research_resolves_from_structured_context():
    research = ref(ResolvedObjectType.RESEARCH, 100)
    result = resolve(FakeIdentityReader([record(research)]), request(semantic(SemanticReferenceType.RECENT_RESEARCH, "刚才那个研究"), conversation_context=StructuredContext(references=[research])))
    assert result.resolved_references[0].resolved_ref == research.ref


def test_resolved_recent_research_satisfies_redundant_strategy_missing_info():
    research = ref(ResolvedObjectType.RESEARCH, 100)
    frame = TaskSemanticFrame(
        primary_intent=Intent.CONTENT_STRATEGY,
        primary_goal="根据刚才那个研究做选题",
        references=[semantic(SemanticReferenceType.RECENT_RESEARCH, "刚才那个研究")],
        missing_info=["该研究的具体内容或结论", "期望的选题方向或领域"],
        confidence=.95,
    )
    result = resolve(
        FakeIdentityReader([record(research)]),
        ContextResolverInput(
            account_ref=ACCOUNT,
            semantic_frame=frame,
            conversation_context=StructuredContext(references=[research]),
        ),
    )

    assert result.context_facts["active_research_ref"].id == 100
    assert result.blocking_missing_info == []


def test_ambiguous_recent_research_remains_blocking_for_strategy():
    first = ref(ResolvedObjectType.RESEARCH, 100)
    second = ref(ResolvedObjectType.RESEARCH, 101)
    frame = TaskSemanticFrame(
        primary_intent=Intent.CONTENT_STRATEGY,
        primary_goal="根据那个研究做选题",
        references=[semantic(SemanticReferenceType.RECENT_RESEARCH, "那个研究")],
        missing_info=["选题数量"],
        confidence=.9,
    )

    result = resolve(
        FakeIdentityReader([record(first), record(second)]),
        ContextResolverInput(
            account_ref=ACCOUNT,
            semantic_frame=frame,
            conversation_context=StructuredContext(references=[first, second]),
        ),
    )

    assert result.resolved_references == []
    assert len(result.ambiguous_references) == 1
    assert result.blocking_missing_info


def test_invalid_explicit_research_remains_unresolved_for_strategy():
    missing = ref(ResolvedObjectType.RESEARCH, 999)
    frame = TaskSemanticFrame(
        primary_intent=Intent.CONTENT_STRATEGY,
        primary_goal="根据这个研究做选题",
        references=[semantic(SemanticReferenceType.ACTIVE_RESEARCH, "这个研究")],
        missing_info=["选题偏好"],
        confidence=.9,
    )

    result = resolve(
        FakeIdentityReader([]),
        ContextResolverInput(account_ref=ACCOUNT, semantic_frame=frame, explicit_references=[missing]),
    )

    assert result.resolved_references == []
    assert result.unresolved_references[0].reason == "REFERENCE_NOT_FOUND"
    assert result.blocking_missing_info


def opportunity_context(*ids, strategy=100):
    strategy_ref = ref(ResolvedObjectType.CONTENT_STRATEGY, strategy)
    opportunities = [ref(ResolvedObjectType.CONTENT_OPPORTUNITY, item) for item in ids]
    return StructuredContext(opportunity_collections=[OpportunityCollection(strategy_ref=strategy_ref, opportunity_refs=opportunities)]), opportunities


def test_ordinal_is_one_based_and_resolves_second_opportunity():
    context, opportunities = opportunity_context(201, 202, 203)
    reader = FakeIdentityReader([record(item) for item in opportunities])
    result = resolve(reader, request(semantic(SemanticReferenceType.ORDINAL_OPPORTUNITY, "第二个选题", ordinal=2), active_context=context))
    assert result.resolved_references[0].resolved_ref.id == 202


def test_ordinal_out_of_range_is_unresolved():
    context, opportunities = opportunity_context(201)
    result = resolve(FakeIdentityReader([record(item) for item in opportunities]), request(semantic(SemanticReferenceType.ORDINAL_OPPORTUNITY, "第二个选题", ordinal=2), active_context=context))
    assert result.unresolved_references[0].reason == "ORDINAL_OUT_OF_RANGE"


def test_two_opportunity_collections_are_ambiguous():
    first, first_refs = opportunity_context(201, 202, strategy=100)
    second, second_refs = opportunity_context(301, 302, strategy=101)
    context = StructuredContext(opportunity_collections=first.opportunity_collections + second.opportunity_collections)
    result = resolve(FakeIdentityReader([record(item) for item in first_refs + second_refs]), request(semantic(SemanticReferenceType.ORDINAL_OPPORTUNITY, "第二个选题", ordinal=2), active_context=context))
    assert [item.id for item in result.ambiguous_references[0].candidate_refs] == [202, 302]


def published(identity, day, account=ACCOUNT):
    item = ref(ResolvedObjectType.PUBLISHED_NOTE, identity, account)
    return record(item, datetime(2026, 9, day, 9, tzinfo=UTC))


@pytest.mark.parametrize(("records", "resolved", "ambiguous", "unresolved"), [([published(1, 21)], 1, 0, 0), ([published(1, 21), published(2, 21)], None, 1, 0), ([], None, 0, 1)])
def test_yesterday_temporal_resolution(records, resolved, ambiguous, unresolved):
    result = resolve(FakeIdentityReader(records), request(semantic(SemanticReferenceType.TEMPORAL_PUBLISHED_NOTE, "昨天发的那篇", temporal_hint="YESTERDAY")))
    assert (result.resolved_references[0].resolved_ref.id if result.resolved_references else None) == resolved
    assert len(result.ambiguous_references) == ambiguous
    assert len(result.unresolved_references) == unresolved


def test_plain_that_note_does_not_select_latest():
    result = resolve(FakeIdentityReader([published(1, 20), published(2, 21)]), request(semantic(SemanticReferenceType.ACTIVE_PUBLISHED_NOTE, "那篇")))
    assert result.unresolved_references[0].reason == "REFERENCE_CONTEXT_MISSING"


def test_explicit_latest_note_uses_deterministic_ordering():
    result = resolve(FakeIdentityReader([published(1, 20), published(2, 21)]), request(semantic(SemanticReferenceType.LATEST_PUBLISHED_NOTE, "最近发布的一篇")))
    assert result.resolved_references[0].resolved_ref.id == 2


def test_account_boundary_rejects_other_account_draft():
    foreign = ref(ResolvedObjectType.DRAFT, 100, account=8)
    result = resolve(FakeIdentityReader([record(foreign)]), request(semantic(SemanticReferenceType.ACTIVE_DRAFT, "这篇"), workspace_selection=StructuredContext(references=[foreign])))
    assert result.unresolved_references[0].reason == "CONTEXT_ACCOUNT_MISMATCH"


def test_pending_unique_draft_resolves_this_one():
    draft = ref(ResolvedObjectType.DRAFT, 100)
    result = resolve(FakeIdentityReader([record(draft)]), request(semantic(SemanticReferenceType.ACTIVE_DRAFT, "就这个"), pending_context=StructuredContext(references=[draft])))
    assert result.resolved_references[0].resolved_ref == draft.ref
    assert result.resolved_references[0].resolution_source == "PENDING_CONTEXT"


@pytest.mark.parametrize("raw_text", ["这个", "这个选题", "刚才选的这个", "它"])
def test_content_create_deictic_resolves_unique_workspace_opportunity(raw_text):
    strategy = ref(ResolvedObjectType.CONTENT_STRATEGY, 100)
    opportunity = ref(ResolvedObjectType.CONTENT_OPPORTUNITY, 201)
    workspace = StructuredContext(references=[opportunity])
    recent = StructuredContext(
        references=[strategy],
        opportunity_collections=[OpportunityCollection(strategy_ref=strategy, opportunity_refs=[opportunity])],
    )
    frame = TaskSemanticFrame(
        primary_intent=Intent.CONTENT_CREATE,
        references=[semantic(SemanticReferenceType.UNKNOWN, raw_text)],
        constraints=["语气自然一点"],
        confidence=.95,
    )
    result = resolve(
        FakeIdentityReader([record(opportunity), record(strategy)]),
        ContextResolverInput(account_ref=ACCOUNT, semantic_frame=frame, workspace_selection=workspace, conversation_context=recent),
    )
    assert result.resolved_references[0].resolved_ref == opportunity.ref
    assert result.resolved_references[0].resolution_source == "WORKSPACE_SELECTION"
    assert result.context_facts["active_strategy_ref"] == strategy.ref
    assert result.blocking_missing_info == []


@pytest.mark.parametrize(
    ("intent", "expected_type"),
    [
        (Intent.CONTENT_STRATEGY, ResolvedObjectType.RESEARCH),
        (Intent.CONTENT_CREATE, ResolvedObjectType.CONTENT_OPPORTUNITY),
        (Intent.CONTENT_REFINE, ResolvedObjectType.DRAFT),
    ],
)
def test_deictic_uses_intent_required_type_when_workspace_has_multiple_types(intent, expected_type):
    items = [
        ref(ResolvedObjectType.RESEARCH, 101),
        ref(ResolvedObjectType.CONTENT_OPPORTUNITY, 201),
        ref(ResolvedObjectType.DRAFT, 301),
    ]
    frame = TaskSemanticFrame(
        primary_intent=intent,
        references=[semantic(SemanticReferenceType.UNKNOWN, "这个")],
        confidence=.95,
    )
    result = resolve(
        FakeIdentityReader([record(item) for item in items]),
        ContextResolverInput(account_ref=ACCOUNT, semantic_frame=frame, workspace_selection=StructuredContext(references=items)),
    )
    assert result.resolved_references[0].resolved_object_type == expected_type
    assert result.ambiguous_references == []


def test_deictic_does_not_substitute_wrong_type_or_bypass_account_boundary():
    research = ref(ResolvedObjectType.RESEARCH, 101)
    frame = TaskSemanticFrame(primary_intent=Intent.CONTENT_CREATE, references=[semantic(SemanticReferenceType.UNKNOWN, "这个")], confidence=.95)
    missing = resolve(
        FakeIdentityReader([record(research)]),
        ContextResolverInput(account_ref=ACCOUNT, semantic_frame=frame, workspace_selection=StructuredContext(references=[research])),
    )
    assert missing.unresolved_references[0].reason == "REFERENCE_CONTEXT_MISSING"

    foreign = ref(ResolvedObjectType.CONTENT_OPPORTUNITY, 201, account=8)
    rejected = resolve(
        FakeIdentityReader([record(foreign)]),
        ContextResolverInput(account_ref=ACCOUNT, semantic_frame=frame, workspace_selection=StructuredContext(references=[foreign])),
    )
    assert rejected.unresolved_references[0].reason == "CONTEXT_ACCOUNT_MISMATCH"


def test_deictic_multiple_same_type_workspace_candidates_are_ambiguous():
    opportunities = [ref(ResolvedObjectType.CONTENT_OPPORTUNITY, item) for item in (201, 202)]
    frame = TaskSemanticFrame(primary_intent=Intent.CONTENT_CREATE, references=[semantic(SemanticReferenceType.UNKNOWN, "这个")], confidence=.95)
    result = resolve(
        FakeIdentityReader([record(item) for item in opportunities]),
        ContextResolverInput(account_ref=ACCOUNT, semantic_frame=frame, workspace_selection=StructuredContext(references=opportunities)),
    )
    assert [item.id for item in result.ambiguous_references[0].candidate_refs] == [201, 202]


@pytest.mark.parametrize(
    ("intent", "kind", "identity"),
    [
        (Intent.CONTENT_REFINE, ResolvedObjectType.DRAFT, 301),
        (Intent.CONTENT_CREATE, ResolvedObjectType.CONTENT_OPPORTUNITY, 201),
        (Intent.CONTENT_STRATEGY, ResolvedObjectType.RESEARCH, 101),
    ],
)
def test_empty_semantic_references_resolve_unique_required_workspace_candidate(intent, kind, identity):
    candidate = ref(kind, identity)
    frame = TaskSemanticFrame(primary_intent=intent, primary_goal="执行当前任务", references=[], confidence=.85)
    result = resolve(
        FakeIdentityReader([record(candidate)]),
        ContextResolverInput(
            account_ref=ACCOUNT,
            semantic_frame=frame,
            workspace_selection=StructuredContext(references=[candidate]),
        ),
    )
    assert result.resolved_references[0].resolved_ref == candidate.ref
    assert result.resolved_references[0].resolution_source == "WORKSPACE_SELECTION"
    assert result.blocking_missing_info == []


def test_empty_references_use_intent_type_not_other_workspace_objects():
    draft = ref(ResolvedObjectType.DRAFT, 301)
    opportunity = ref(ResolvedObjectType.CONTENT_OPPORTUNITY, 201)
    frame = TaskSemanticFrame(primary_intent=Intent.CONTENT_REFINE, primary_goal="修改草稿", references=[], confidence=.85)
    result = resolve(
        FakeIdentityReader([record(draft), record(opportunity)]),
        ContextResolverInput(
            account_ref=ACCOUNT,
            semantic_frame=frame,
            workspace_selection=StructuredContext(references=[opportunity, draft]),
        ),
    )
    assert [item.resolved_ref for item in result.resolved_references] == [draft.ref]


def test_empty_references_do_not_substitute_wrong_workspace_type():
    opportunity = ref(ResolvedObjectType.CONTENT_OPPORTUNITY, 201)
    frame = TaskSemanticFrame(primary_intent=Intent.CONTENT_REFINE, primary_goal="修改草稿", references=[], confidence=.85)
    result = resolve(
        FakeIdentityReader([record(opportunity)]),
        ContextResolverInput(
            account_ref=ACCOUNT,
            semantic_frame=frame,
            workspace_selection=StructuredContext(references=[opportunity]),
        ),
    )
    assert result.resolved_references == []
    assert result.unresolved_references == []


def test_empty_references_make_multiple_required_workspace_candidates_ambiguous():
    drafts = [ref(ResolvedObjectType.DRAFT, item) for item in (301, 302)]
    frame = TaskSemanticFrame(primary_intent=Intent.CONTENT_REFINE, primary_goal="修改草稿", references=[], confidence=.85)
    result = resolve(
        FakeIdentityReader([record(item) for item in drafts]),
        ContextResolverInput(
            account_ref=ACCOUNT,
            semantic_frame=frame,
            workspace_selection=StructuredContext(references=drafts),
        ),
    )
    assert [item.id for item in result.ambiguous_references[0].candidate_refs] == [301, 302]
    assert result.blocking_missing_info


def test_empty_references_preserve_explicit_invalid_and_valid_priority_over_workspace():
    missing = ref(ResolvedObjectType.DRAFT, 999)
    explicit = ref(ResolvedObjectType.DRAFT, 302)
    workspace = ref(ResolvedObjectType.DRAFT, 301)
    frame = TaskSemanticFrame(primary_intent=Intent.CONTENT_REFINE, primary_goal="修改草稿", references=[], confidence=.85)

    invalid = resolve(
        FakeIdentityReader([record(workspace)]),
        ContextResolverInput(
            account_ref=ACCOUNT,
            semantic_frame=frame,
            explicit_references=[missing],
            workspace_selection=StructuredContext(references=[workspace]),
        ),
    )
    assert invalid.resolved_references == []
    assert invalid.unresolved_references[0].reason == "REFERENCE_NOT_FOUND"

    valid = resolve(
        FakeIdentityReader([record(explicit), record(workspace)]),
        ContextResolverInput(
            account_ref=ACCOUNT,
            semantic_frame=frame,
            explicit_references=[explicit],
            workspace_selection=StructuredContext(references=[workspace]),
        ),
    )
    assert valid.resolved_references[0].resolved_ref == explicit.ref
    assert valid.resolved_references[0].resolution_source == "EXPLICIT_SELECTION"


def test_empty_references_reject_foreign_workspace_candidate():
    foreign = ref(ResolvedObjectType.DRAFT, 301, account=8)
    frame = TaskSemanticFrame(primary_intent=Intent.CONTENT_REFINE, primary_goal="修改草稿", references=[], confidence=.85)
    result = resolve(
        FakeIdentityReader([record(foreign)]),
        ContextResolverInput(
            account_ref=ACCOUNT,
            semantic_frame=frame,
            workspace_selection=StructuredContext(references=[foreign]),
        ),
    )
    assert result.resolved_references == []
    assert result.unresolved_references[0].reason == "CONTEXT_ACCOUNT_MISMATCH"


def test_explicit_unresolved_semantic_reference_is_not_masked_by_workspace_default():
    workspace = ref(ResolvedObjectType.DRAFT, 301)
    missing = ref(ResolvedObjectType.DRAFT, 999)
    frame = TaskSemanticFrame(
        primary_intent=Intent.CONTENT_REFINE,
        primary_goal="修改草稿",
        references=[semantic(SemanticReferenceType.ACTIVE_DRAFT, "明确指定的草稿")],
        confidence=.9,
    )
    result = resolve(
        FakeIdentityReader([record(workspace)]),
        ContextResolverInput(
            account_ref=ACCOUNT,
            semantic_frame=frame,
            explicit_references=[missing],
            workspace_selection=StructuredContext(references=[workspace]),
        ),
    )
    assert result.resolved_references == []
    assert result.unresolved_references[0].reason == "REFERENCE_NOT_FOUND"


def test_turn96_and_turn103_semantic_shapes_resolve_same_workspace_draft():
    draft = ref(ResolvedObjectType.DRAFT, 2625)
    workspace = StructuredContext(references=[draft])
    reader = FakeIdentityReader([record(draft)])
    frames = [
        TaskSemanticFrame(
            primary_intent=Intent.CONTENT_REFINE,
            primary_goal="修改开头和语气",
            references=[semantic(SemanticReferenceType.ACTIVE_DRAFT, "这个开头")],
            confidence=.9,
        ),
        TaskSemanticFrame(
            primary_intent=Intent.CONTENT_REFINE,
            primary_goal="修改开头和语气",
            references=[],
            confidence=.85,
        ),
    ]
    results = [
        resolve(reader, ContextResolverInput(account_ref=ACCOUNT, semantic_frame=frame, workspace_selection=workspace))
        for frame in frames
    ]
    assert [result.resolved_references[0].resolved_ref.id for result in results] == [2625, 2625]
    assert all(result.blocking_missing_info == [] for result in results)


def test_recent_run_is_only_resolved_not_cancelled():
    run = ref(ResolvedObjectType.RUN, "wfr_123")
    data = ContextResolverInput(account_ref=ACCOUNT, semantic_frame=TaskSemanticFrame(primary_intent=Intent.CANCEL_TASK, references=[semantic(SemanticReferenceType.RECENT_RUN, "刚才那个任务")], confidence=1), conversation_context=StructuredContext(references=[run]))
    reader = FakeIdentityReader([record(run)])
    result = resolve(reader, data)
    assert result.resolved_references[0].resolved_ref == run.ref
    assert reader.writes == reader.llm_calls == 0


def test_unresolved_and_ambiguous_become_blocking_info_without_execution():
    context, refs = opportunity_context(1, 2)
    context.opportunity_collections.append(OpportunityCollection(strategy_ref=ref(ResolvedObjectType.CONTENT_STRATEGY, 101), opportunity_refs=refs))
    frame = TaskSemanticFrame(primary_intent=Intent.CONTENT_CREATE, references=[semantic(SemanticReferenceType.ACTIVE_DRAFT, "这篇"), semantic(SemanticReferenceType.ORDINAL_OPPORTUNITY, "第一个", ordinal=1)], missing_info=["缺少语气要求"], confidence=.8)
    result = resolve(FakeIdentityReader([record(item) for item in refs]), ContextResolverInput(account_ref=ACCOUNT, semantic_frame=frame, active_context=context))
    assert len(result.unresolved_references) == 1 and len(result.ambiguous_references) == 1
    assert len(result.blocking_missing_info) == 2
    assert "缺少语气要求" not in result.blocking_missing_info


def test_integration_semantic_frame_to_second_opportunity_stops_at_resolution():
    context, refs = opportunity_context(201, 202, 203)
    llm = SemanticFakeLLM({"primary_intent": "CONTENT_CREATE", "primary_goal": "写一篇内容", "references": [{"type": "ORDINAL_OPPORTUNITY", "raw_text": "第二个选题", "ordinal": 2}], "confidence": .95})
    frame = ControlAgentSemanticLayer(llm).understand("用第二个选题帮我写一篇")
    reader = FakeIdentityReader([record(item) for item in refs])
    result = resolve(reader, ContextResolverInput(account_ref=ACCOUNT, semantic_frame=frame, active_context=context))
    assert result.resolved_references[0].resolved_ref.id == 202
    assert llm.calls == 1
    assert reader.writes == reader.llm_calls == 0


def test_integration_temporal_post_review_stops_at_resolution():
    llm = SemanticFakeLLM({"primary_intent": "POST_PUBLISH_REVIEW", "primary_goal": "分析私信转化", "references": [{"type": "TEMPORAL_PUBLISHED_NOTE", "raw_text": "昨天发的那篇", "temporal_hint": "YESTERDAY"}], "confidence": .95})
    frame = ControlAgentSemanticLayer(llm).understand("看看昨天发的那篇为什么没人私信")
    reader = FakeIdentityReader([published(500, 21)])
    result = resolve(reader, ContextResolverInput(account_ref=ACCOUNT, semantic_frame=frame))
    assert result.resolved_references[0].resolved_ref.id == 500
    assert llm.calls == 1
    assert reader.writes == reader.llm_calls == 0


def test_architecture_has_no_llm_tool_workflow_runtime_http_or_writes():
    root = Path(__file__).resolve().parents[1] / "app" / "agent" / "context"
    source = "\n".join(path.read_text(encoding="utf-8") for path in root.glob("*.py"))
    forbidden = ("app.llm", "app.agent.tools", "app.agent.workflows", "app.runtime", "requests", "httpx", ".commit(", ".add(", ".flush(", "AgentRuntime")
    assert [token for token in forbidden if token in source] == []
