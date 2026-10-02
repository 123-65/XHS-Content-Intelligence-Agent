from datetime import UTC, datetime
from types import SimpleNamespace

from app.agent.context.contracts import IdentityRecord, ObjectRef, ResolvedObjectType, StructuredContext, TrustedContextRef
from app.agent.context.resolver import ContextResolver
from app.agent.control.orchestrator import AgentTurnOrchestrator
from app.agent.control.semantic_layer import ControlAgentSemanticLayer
from app.agent.control.turn_contracts import AgentTurnInput, TurnContextState
from app.agent.planning.execution_service import PlanExecutionService
from app.agent.planning.planner import DeterministicPlanner
from app.agent.schemas.execution import RuntimeAction, WorkflowStatus
from app.agent.schemas.interaction import PendingInteraction, PendingInteractionType
from app.agent.tools.access_scopes import EvidenceAccessScope
from app.agent.tools.execution_context import ToolExecutionContext
from app.agent.tools.xhs_contracts import CollectionAccessScope, CollectionAuthorizationSource


NOW = datetime(2026, 9, 22, 12, tzinfo=UTC)


class SemanticClient:
    def __init__(self, *outputs): self.outputs = list(outputs)
    def generate_structured(self, **kwargs): return SimpleNamespace(data=self.outputs.pop(0))


class Reader:
    def __init__(self, records=()): self.records = {item.ref: item for item in records}
    def get_identity(self, ref): return self.records.get(ref)
    def list_published_between(self, account_ref, start, end):
        return [item for item in self.records.values() if item.ref.type == ResolvedObjectType.PUBLISHED_NOTE and item.account_ref == account_ref and item.published_at and start <= item.published_at < end]
    def latest_published(self, account_ref): return None


class ContextOwner:
    def __init__(self): self.states = {}; self.saves = 0
    def load(self, conversation_id, account_ref): return self.states.get(conversation_id, TurnContextState()).model_copy(deep=True)
    def save(self, conversation_id, account_ref, state):
        self.saves += 1
        if conversation_id is not None: self.states[conversation_id] = state.model_copy(deep=True)


class Runtime:
    def __init__(self, starts=(), resumes=()):
        self.starts, self.resumes = list(starts), list(resumes)
        self.start_calls, self.resume_calls, self.get_calls = [], [], []
        self.current = None

    def start(self, request, context):
        self.start_calls.append(request)
        value = self.starts.pop(0)
        self.current = value
        return value

    def get_run(self, run_ref):
        self.get_calls.append(run_ref)
        return self.current

    def resume(self, request, context):
        self.resume_calls.append(request)
        value = self.resumes.pop(0)
        self.current = value
        return value


def runtime_result(status, *, run="run_1", checkpoint=2, pending=None, result=None, workflow="RESEARCH_V1"):
    return SimpleNamespace(run_ref=run, workflow_name=workflow, account_ref=7, status=status, checkpoint_version=checkpoint, pending_interaction=pending, result=result, warnings=[], error=None)


def semantic(intent, **updates):
    value = {"primary_intent": intent, "primary_goal": "完成当前目标", "confidence": .95}
    value.update(updates)
    return value


def trusted(kind, identity, published_at=None):
    item = TrustedContextRef(ref=ObjectRef(type=kind, id=identity), account_ref=7)
    return item, IdentityRecord(ref=item.ref, account_ref=7, published_at=published_at)


def build(outputs, reader=None, runtime=None, owner=None, handlers=None):
    runtime = runtime or Runtime()
    owner = owner or ContextOwner()
    orchestrator = AgentTurnOrchestrator(
        semantic_layer=ControlAgentSemanticLayer(SemanticClient(*outputs)),
        context_resolver=ContextResolver(reader or Reader(), now=lambda: NOW),
        planner=DeterministicPlanner(now=lambda: NOW),
        plan_execution_service=PlanExecutionService(runtime),
        runtime=runtime,
        context_owner=owner,
        action_handlers=handlers,
    )
    return orchestrator, runtime, owner


def collection_context(*profile_urls, account=7):
    return ToolExecutionContext(
        db=None,
        evidence_access_scope=EvidenceAccessScope.deny_all(),
        collection_access_scope=CollectionAccessScope(
            workspace_account_ref=account,
            authorization_source=CollectionAuthorizationSource.USER_PROVIDED,
            allowed_profile_urls=profile_urls,
        ),
    )


def note_collection_context(*note_urls, account=7):
    return ToolExecutionContext(
        db=None,
        evidence_access_scope=EvidenceAccessScope.deny_all(),
        collection_access_scope=CollectionAccessScope(
            workspace_account_ref=account,
            authorization_source=CollectionAuthorizationSource.USER_PROVIDED,
            allowed_note_urls=note_urls,
        ),
    )


def profile_url(identity="profile-1", *, token=True):
    suffix = "?xsec_token=authorized-token" if token else ""
    return f"https://www.xiaohongshu.com/user/profile/{identity}{suffix}"


def test_research_profile_material_satisfies_profile_reference_and_starts_runtime():
    url = profile_url()
    app, runtime, _ = build(
        [semantic("RESEARCH", references=[{"type": "PROFILE", "raw_text": "该账号"}])],
        runtime=Runtime(starts=[runtime_result(WorkflowStatus.WAITING_USER)]),
    )
    result = app.handle_turn(
        AgentTurnInput(account_ref=7, text="研究该账号", profile_urls=[url]),
        collection_context(url),
    )
    assert result.run_ref == "run_1"
    assert runtime.start_calls[0].input["profile_urls"] == [url]


def test_structured_profile_material_rejects_semantic_reconstructed_profile_value():
    url = profile_url()
    app, runtime, _ = build(
        [semantic(
            "RESEARCH",
            references=[{"type": "PROFILE", "raw_text": "该账号"}],
            profile_urls=["当前提供的Profile URL"],
        )],
        runtime=Runtime(starts=[runtime_result(WorkflowStatus.WAITING_USER)]),
    )
    result = app.handle_turn(
        AgentTurnInput(account_ref=7, text="研究该账号", profile_urls=[url]),
        collection_context(url),
    )
    assert result.run_ref == "run_1"
    assert runtime.start_calls[0].input["profile_urls"] == [url]


def test_bare_authorized_profile_is_material_but_unauthorized_profile_is_not():
    bare = profile_url(token=False)
    authorized = profile_url("other")
    turn = AgentTurnInput(account_ref=7, text="研究该账号", profile_urls=[bare])
    materials = AgentTurnOrchestrator._current_turn_materials(turn, collection_context(bare))
    assert len(materials) == 1 and materials[0].source_url == bare
    assert AgentTurnOrchestrator._current_turn_materials(turn, collection_context(authorized)) == []


def test_current_turn_xhs_url_is_removed_from_canonical_reference_candidates():
    url = profile_url()
    app, runtime, _ = build(
        [semantic("RESEARCH", references=[{"type": "UNKNOWN", "raw_text": url}])],
        runtime=Runtime(starts=[runtime_result(WorkflowStatus.WAITING_USER)]),
    )

    result = app.handle_turn(
        AgentTurnInput(account_ref=7, text=f"研究这个账号：{url}", profile_urls=[url]),
        collection_context(url),
    )

    assert result.run_ref == "run_1"
    assert runtime.start_calls[0].input["profile_urls"] == [url]


def test_pending_research_material_follow_up_starts_exactly_one_research_run():
    url = profile_url()
    waiting = PendingInteraction(
        type=PendingInteractionType.CLARIFICATION,
        reason="请提供要分析的小红书账号或笔记链接。",
        required_fields=["research_material"],
        resume_token="RESEARCH_V1_RESUME",
    )
    runtime = Runtime(starts=[runtime_result(WorkflowStatus.WAITING_USER, pending=waiting)])
    app, _, owner = build(
        [
            semantic("RESEARCH", primary_goal="分析同行账号", references=[{"type": "PROFILE", "raw_text": "同行账号"}]),
            semantic("UNKNOWN", primary_goal="确认用户意图", confidence=.4),
        ],
        runtime=runtime,
    )

    first = app.handle_turn(AgentTurnInput(account_ref=7, text="帮我分析一个同行账号。", conversation_id=9), None)
    second = app.handle_turn(
        AgentTurnInput(account_ref=7, text=url, conversation_id=9, profile_urls=[url]),
        collection_context(url),
    )

    assert first.status == WorkflowStatus.WAITING_USER
    assert first.pending_interaction.required_fields == ["research_material"]
    assert first.message == "请提供要分析的小红书账号或笔记链接。"
    assert second.run_ref == "run_1"
    assert len(runtime.start_calls) == 1
    assert runtime.resume_calls == []
    assert runtime.start_calls[0].input["research_goal"] == "分析同行账号"
    assert runtime.start_calls[0].input["profile_urls"] == [url]
    assert owner.states[9].active_pending_run_ref == "run_1"


def test_research_profile_without_semantic_reference_keeps_original_input_path():
    url = profile_url()
    app, runtime, _ = build(
        [semantic("RESEARCH", references=[])],
        runtime=Runtime(starts=[runtime_result(WorkflowStatus.WAITING_USER)]),
    )
    result = app.handle_turn(
        AgentTurnInput(account_ref=7, text="研究资料", profile_urls=[url]),
        collection_context(url),
    )
    assert result.run_ref == "run_1"
    assert runtime.start_calls[0].input["profile_urls"] == [url]


def test_turn_materials_are_visible_to_semantic_parsing():
    turn = AgentTurnInput(
        account_ref=7,
        text="研究这些材料",
        note_urls=["https://www.xiaohongshu.com/explore/note-1"],
        profile_urls=["https://www.xiaohongshu.com/user/profile/user-1"],
    )

    semantic_text = AgentTurnOrchestrator._semantic_turn_text(turn)

    assert semantic_text.startswith("研究这些材料")
    assert "note_urls=1 条，profile_urls=1 条" in semantic_text
    assert "https://www.xiaohongshu.com" not in semantic_text
    assert "不要把 URL 解析为 references" in semantic_text


def test_create_from_second_opportunity_runs_only_creation():
    strategy, strategy_record = trusted(ResolvedObjectType.CONTENT_STRATEGY, 100)
    opportunity, opportunity_record = trusted(ResolvedObjectType.CONTENT_OPPORTUNITY, 202)
    output = runtime_result(WorkflowStatus.SUCCESS, result={"status": "SUCCESS", "draft_ref": 300}, workflow="CONTENT_CREATION_V1")
    app, runtime, _ = build([semantic("CONTENT_CREATE", constraints=["自然一点"], references=[{"type": "ORDINAL_OPPORTUNITY", "raw_text": "第二个选题", "ordinal": 2}])], Reader([strategy_record, opportunity_record]), Runtime(starts=[output]))
    workspace = StructuredContext(references=[strategy], opportunity_collections=[{"strategy_ref": strategy, "opportunity_refs": [trusted(ResolvedObjectType.CONTENT_OPPORTUNITY, 201)[0], opportunity]}])
    result = app.handle_turn(AgentTurnInput(account_ref=7, text="用第二个选题写一篇", conversation_id=1), None, workspace_selection=workspace)
    assert result.status == WorkflowStatus.SUCCESS
    assert len(runtime.start_calls) == 1
    assert runtime.start_calls[0].workflow_name == "CONTENT_CREATION_V1"
    assert runtime.start_calls[0].input["opportunity_ref"] == 202


def test_create_from_deictic_workspace_opportunity_is_ready_and_preserves_constraint():
    strategy, strategy_record = trusted(ResolvedObjectType.CONTENT_STRATEGY, 100)
    opportunity, opportunity_record = trusted(ResolvedObjectType.CONTENT_OPPORTUNITY, 202)
    output = runtime_result(WorkflowStatus.SUCCESS, result={"status": "SUCCESS", "draft_ref": 300}, workflow="CONTENT_CREATION_V1")
    app, runtime, owner = build(
        [semantic("CONTENT_CREATE", references=[{"type": "UNKNOWN", "raw_text": "这个"}], constraints=["语气自然一点"])],
        Reader([strategy_record, opportunity_record]),
        Runtime(starts=[output]),
    )
    owner.states[1] = TurnContextState(
        recent_context=StructuredContext(
            references=[strategy],
            opportunity_collections=[{"strategy_ref": strategy, "opportunity_refs": [opportunity]}],
        )
    )
    result = app.handle_turn(
        AgentTurnInput(account_ref=7, text="用这个写一篇，语气自然一点。", conversation_id=1),
        None,
        workspace_selection=StructuredContext(references=[opportunity]),
    )
    assert result.status == WorkflowStatus.SUCCESS
    assert runtime.start_calls[0].workflow_name == "CONTENT_CREATION_V1"
    assert runtime.start_calls[0].input["opportunity_ref"] == 202
    assert runtime.start_calls[0].input["strategy_artifact_ref"]["id"] == 100
    assert runtime.start_calls[0].input["style_constraints"] == ["语气自然一点"]


def test_active_draft_refinement_starts_runtime():
    draft, draft_record = trusted(ResolvedObjectType.DRAFT, 100)
    output = runtime_result(WorkflowStatus.SUCCESS, result={"draft_ref": 100}, workflow="CONTENT_REFINEMENT_V1")
    app, runtime, _ = build([semantic("CONTENT_REFINE", primary_goal="自然一点", references=[{"type": "ACTIVE_DRAFT", "raw_text": "这篇"}])], Reader([draft_record]), Runtime(starts=[output]))
    result = app.handle_turn(AgentTurnInput(account_ref=7, text="这篇自然一点"), None, workspace_selection=StructuredContext(references=[draft]))
    assert result.artifacts[0].id == 100 and runtime.start_calls[0].workflow_name == "CONTENT_REFINEMENT_V1"


def test_turn96_and_turn103_semantics_both_start_refinement_from_same_workspace():
    draft, draft_record = trusted(ResolvedObjectType.DRAFT, 2625)
    outputs = [
        semantic("CONTENT_REFINE", primary_goal="修改开头和语气", references=[{"type": "ACTIVE_DRAFT", "raw_text": "这个开头"}]),
        semantic("CONTENT_REFINE", primary_goal="修改开头和语气", references=[]),
    ]
    runtime = Runtime(starts=[
        runtime_result(WorkflowStatus.SUCCESS, run="run_96", result={"draft_ref": 2625}, workflow="CONTENT_REFINEMENT_V1"),
        runtime_result(WorkflowStatus.SUCCESS, run="run_103", result={"draft_ref": 2625}, workflow="CONTENT_REFINEMENT_V1"),
    ])
    app, _, _ = build(outputs, Reader([draft_record]), runtime)
    workspace = StructuredContext(references=[draft])

    first = app.handle_turn(AgentTurnInput(account_ref=7, text="修改开头和语气", conversation_id=96), None, workspace_selection=workspace)
    second = app.handle_turn(AgentTurnInput(account_ref=7, text="修改开头和语气", conversation_id=103), None, workspace_selection=workspace)

    assert first.status == second.status == WorkflowStatus.SUCCESS
    assert [call.workflow_name for call in runtime.start_calls] == ["CONTENT_REFINEMENT_V1", "CONTENT_REFINEMENT_V1"]
    assert [call.input["draft_ref"] for call in runtime.start_calls] == [2625, 2625]


def test_missing_draft_and_ambiguous_note_clarify_without_runtime():
    app, runtime, _ = build([semantic("CONTENT_REFINE", references=[{"type": "ACTIVE_DRAFT", "raw_text": "这篇"}])])
    result = app.handle_turn(AgentTurnInput(account_ref=7, text="这篇自然一点"), None)
    assert result.action == RuntimeAction.CLARIFY and result.pending_interaction
    assert runtime.start_calls == []


def test_start_waiting_then_reply_resumes_same_run_without_new_start():
    pending1 = PendingInteraction(type=PendingInteractionType.CLARIFICATION, reason="请补充链接", required_fields=["note_urls"], related_run_ref="run_1", resume_token="r1")
    waiting = runtime_result(WorkflowStatus.WAITING_USER, pending=pending1, checkpoint=2)
    success = runtime_result(WorkflowStatus.SUCCESS, checkpoint=4, result={"research_artifact_ref": {"type": "RESEARCH", "id": 100}})
    runtime, owner = Runtime(starts=[waiting], resumes=[success]), ContextOwner()
    app, _, _ = build([semantic("RESEARCH", note_urls=["https://xhs/1"]), semantic("UNKNOWN", primary_goal="补充第二个链接", note_urls=["https://xhs/2"])], runtime=runtime, owner=owner)
    first = app.handle_turn(AgentTurnInput(account_ref=7, text="研究这个链接", conversation_id=9), None)
    second = app.handle_turn(AgentTurnInput(account_ref=7, text="再补这个", conversation_id=9), None)
    assert first.run_ref == second.run_ref == "run_1"
    assert len(runtime.start_calls) == 1 and len(runtime.resume_calls) == 1
    assert runtime.resume_calls[0].expected_checkpoint_version == 2
    assert owner.states[9].active_pending_run_ref is None
    assert owner.states[9].recent_context.references[0].ref.id == 100


def test_resume_waiting_keeps_same_run_and_new_checkpoint():
    pending = PendingInteraction(type=PendingInteractionType.CLARIFICATION, reason="还需资料", required_fields=["note_urls"], related_run_ref="run_1", resume_token="r2")
    owner = ContextOwner()
    owner.states[1] = TurnContextState(active_pending_run_ref="run_1", active_pending_checkpoint_version=2, active_pending_interaction=pending)
    current = runtime_result(WorkflowStatus.WAITING_USER, pending=pending, checkpoint=2)
    again = runtime_result(WorkflowStatus.WAITING_USER, pending=pending, checkpoint=4)
    runtime = Runtime(resumes=[again]); runtime.current = current
    app, _, _ = build([semantic("UNKNOWN", primary_goal="补充资料", note_urls=["https://xhs/2"])], runtime=runtime, owner=owner)
    result = app.handle_turn(AgentTurnInput(account_ref=7, text="补充资料", conversation_id=1), None)
    assert result.run_ref == "run_1" and result.checkpoint_version == 4
    assert owner.states[1].active_pending_checkpoint_version == 4


def test_resume_authoritative_note_materials_override_invalid_semantic_reconstruction():
    notes = [
        "https://www.xiaohongshu.com/explore/note-1?xsec_token=token-1",
        "https://www.xiaohongshu.com/explore/note-2?xsec_token=token-2",
        "https://www.xiaohongshu.com/explore/note-3?xsec_token=token-3",
    ]
    pending = PendingInteraction(
        type=PendingInteractionType.CLARIFICATION,
        reason="please provide note URLs",
        required_fields=["note_urls", "evidence_refs"],
        related_run_ref="run_1",
        resume_token="RESEARCH_V1_RESUME",
    )
    owner = ContextOwner()
    owner.states[1] = TurnContextState(
        active_pending_run_ref="run_1",
        active_pending_checkpoint_version=3,
        active_pending_interaction=pending,
    )
    current = runtime_result(WorkflowStatus.WAITING_USER, pending=pending, checkpoint=3)
    success = runtime_result(
        WorkflowStatus.SUCCESS,
        checkpoint=5,
        result={"research_artifact_ref": {"type": "RESEARCH", "id": 100}},
    )
    runtime = Runtime(resumes=[success])
    runtime.current = current
    app, _, _ = build(
        [semantic("UNKNOWN", note_urls=["first note", "second note", "third note"])],
        runtime=runtime,
        owner=owner,
    )

    result = app.handle_turn(
        AgentTurnInput(account_ref=7, text="supplement notes", conversation_id=1, note_urls=notes),
        note_collection_context(*notes),
    )

    assert result.status == WorkflowStatus.SUCCESS
    assert runtime.resume_calls[0].run_ref == "run_1"
    assert runtime.resume_calls[0].expected_checkpoint_version == 3
    assert runtime.resume_calls[0].new_input["note_urls"] == notes


def test_authoritative_note_material_deduplicates_semantic_match_and_rejects_semantic_expansion():
    authorized = "https://www.xiaohongshu.com/explore/note-1?xsec_token=token-1"
    unauthorized = "https://www.xiaohongshu.com/explore/note-2?xsec_token=token-2"
    pending = PendingInteraction(type=PendingInteractionType.CLARIFICATION, reason="notes", required_fields=["note_urls"], resume_token="r")
    owner = ContextOwner()
    owner.states[1] = TurnContextState(active_pending_run_ref="run_1", active_pending_checkpoint_version=2, active_pending_interaction=pending)
    runtime = Runtime(resumes=[runtime_result(WorkflowStatus.SUCCESS, checkpoint=3, result={})])
    runtime.current = runtime_result(WorkflowStatus.WAITING_USER, pending=pending, checkpoint=2)
    app, _, _ = build([semantic("UNKNOWN", note_urls=[authorized, unauthorized])], runtime=runtime, owner=owner)

    app.handle_turn(
        AgentTurnInput(account_ref=7, text="supplement", conversation_id=1, note_urls=[authorized]),
        note_collection_context(authorized),
    )

    assert runtime.resume_calls[0].new_input["note_urls"] == [authorized]


def test_semantic_note_urls_remain_when_current_turn_has_no_structured_note_material():
    semantic_note = "https://www.xiaohongshu.com/explore/note-1?xsec_token=token-1"
    pending = PendingInteraction(type=PendingInteractionType.CLARIFICATION, reason="notes", required_fields=["note_urls"], resume_token="r")
    owner = ContextOwner()
    owner.states[1] = TurnContextState(active_pending_run_ref="run_1", active_pending_checkpoint_version=2, active_pending_interaction=pending)
    runtime = Runtime(resumes=[runtime_result(WorkflowStatus.SUCCESS, checkpoint=3, result={})])
    runtime.current = runtime_result(WorkflowStatus.WAITING_USER, pending=pending, checkpoint=2)
    app, _, _ = build([semantic("UNKNOWN", note_urls=[semantic_note])], runtime=runtime, owner=owner)

    app.handle_turn(AgentTurnInput(account_ref=7, text="supplement", conversation_id=1), None)

    assert runtime.resume_calls[0].new_input["note_urls"] == [semantic_note]


def test_note_material_authority_does_not_cross_account_boundary():
    semantic_note = "https://www.xiaohongshu.com/explore/note-1?xsec_token=semantic-token"
    submitted = "https://www.xiaohongshu.com/explore/note-2?xsec_token=submitted-token"
    turn = AgentTurnInput(account_ref=7, text="supplement", note_urls=[submitted])

    assert AgentTurnOrchestrator._authoritative_current_turn_note_urls(
        turn,
        note_collection_context(submitted, account=8),
    ) == []


def test_pending_general_chat_and_cancel_do_not_resume():
    pending = PendingInteraction(type=PendingInteractionType.CLARIFICATION, reason="补充", resume_token="r")
    for intent in ("GENERAL_CHAT", "CANCEL_TASK"):
        owner = ContextOwner(); owner.states[1] = TurnContextState(active_pending_run_ref="run_1", active_pending_checkpoint_version=2, active_pending_interaction=pending)
        runtime = Runtime(); runtime.current = runtime_result(WorkflowStatus.WAITING_USER, pending=pending)
        app, _, _ = build([semantic(intent)], runtime=runtime, owner=owner)
        result = app.handle_turn(AgentTurnInput(account_ref=7, text="先做别的", conversation_id=1), None)
        assert runtime.resume_calls == []
        assert result.action in {RuntimeAction.RESPOND, RuntimeAction.CANCEL}


def test_general_chat_query_and_update_strategy_never_start_workflow():
    handler = lambda turn, frame: ("账号定位是职场成长", {"positioning": "职场成长"})
    app, runtime, _ = build([semantic("GENERAL_CHAT"), semantic("QUERY_PROFILE"), semantic("UPDATE_STRATEGY", primary_goal="以后别写营销腔")], handlers={"QUERY_PROFILE": handler})
    chat = app.handle_turn(AgentTurnInput(account_ref=7, text="你好"), None)
    query = app.handle_turn(AgentTurnInput(account_ref=7, text="账号定位是什么"), None)
    update = app.handle_turn(AgentTurnInput(account_ref=7, text="以后别写营销腔"), None)
    assert chat.action == RuntimeAction.RESPOND
    assert query.result == {"positioning": "职场成长"}
    assert update.action == RuntimeAction.CONFIRM and update.pending_interaction.type == PendingInteractionType.CONFIRMATION
    assert runtime.start_calls == []


def test_failed_or_waiting_first_multi_goal_never_starts_second():
    note, note_record = trusted(ResolvedObjectType.PUBLISHED_NOTE, 500, NOW)
    draft, draft_record = trusted(ResolvedObjectType.DRAFT, 100)
    for status in (WorkflowStatus.WAITING_USER, WorkflowStatus.FAILED):
        pending = PendingInteraction(type=PendingInteractionType.CLARIFICATION, reason="补充", resume_token="r") if status == WorkflowStatus.WAITING_USER else None
        runtime = Runtime(starts=[runtime_result(status, pending=pending, workflow="POST_PUBLISH_REVIEW_V1")])
        app, _, _ = build([semantic("POST_PUBLISH_REVIEW", sub_goals=["CONTENT_REFINE"], references=[{"type": "ACTIVE_PUBLISHED_NOTE", "raw_text": "那篇"}, {"type": "ACTIVE_DRAFT", "raw_text": "草稿"}])], Reader([note_record, draft_record]), runtime)
        app.handle_turn(AgentTurnInput(account_ref=7, text="分析后重写"), None, workspace_selection=StructuredContext(references=[note, draft]))
        assert len(runtime.start_calls) == 1


def test_recent_research_is_used_next_turn_without_message_scanning():
    research_record = IdentityRecord(ref=ObjectRef(type=ResolvedObjectType.RESEARCH, id=100), account_ref=7)
    reader = Reader([research_record])
    first_runtime = runtime_result(WorkflowStatus.SUCCESS, result={"research_artifact_ref": {"type": "RESEARCH", "id": 100}})
    second_runtime = runtime_result(WorkflowStatus.SUCCESS, run="run_2", result={"strategy_artifact_ref": {"type": "CONTENT_STRATEGY", "id": 200}}, workflow="CONTENT_STRATEGY_V1")
    runtime, owner = Runtime(starts=[first_runtime, second_runtime]), ContextOwner()
    app, _, _ = build([semantic("RESEARCH", note_urls=["https://xhs/1"]), semantic("CONTENT_STRATEGY", references=[{"type": "RECENT_RESEARCH", "raw_text": "刚才那个研究"}])], reader, runtime, owner)
    app.handle_turn(AgentTurnInput(account_ref=7, text="研究这个", conversation_id=3), None)
    result = app.handle_turn(AgentTurnInput(account_ref=7, text="根据刚才那个研究做选题", conversation_id=3), None)
    assert result.status == WorkflowStatus.SUCCESS
    assert runtime.start_calls[1].workflow_name == "CONTENT_STRATEGY_V1"
    assert runtime.start_calls[1].input["research_artifact_ref"]["id"] == 100


def test_recent_research_starts_strategy_when_semantic_only_suggests_preferences():
    research, research_record = trusted(ResolvedObjectType.RESEARCH, 100)
    output = runtime_result(
        WorkflowStatus.SUCCESS,
        result={"strategy_artifact_ref": {"type": "CONTENT_STRATEGY", "id": 200}},
        workflow="CONTENT_STRATEGY_V1",
    )
    app, runtime, owner = build(
        [
            semantic(
                "CONTENT_STRATEGY",
                primary_goal="根据刚才那个研究帮我做选题",
                references=[{"type": "RECENT_RESEARCH", "raw_text": "刚才那个研究"}],
                missing_info=["选题数量", "选题偏好"],
            )
        ],
        Reader([research_record]),
        Runtime(starts=[output]),
    )
    owner.states[3] = TurnContextState(recent_context=StructuredContext(references=[research]))

    result = app.handle_turn(
        AgentTurnInput(account_ref=7, text="根据刚才那个研究帮我做选题", conversation_id=3),
        None,
    )

    assert result.status == WorkflowStatus.SUCCESS
    assert len(runtime.start_calls) == 1
    assert runtime.start_calls[0].workflow_name == "CONTENT_STRATEGY_V1"
    assert runtime.start_calls[0].input["research_artifact_ref"]["id"] == 100


def test_orchestrator_architecture_has_no_direct_tool_or_workflow_execution():
    source = (__import__("pathlib").Path(__file__).resolve().parents[1] / "app" / "agent" / "control" / "orchestrator.py").read_text(encoding="utf-8")
    assert not any(token in source for token in ("build_tool_handler", "build_workflow_handler", ".execute(typed_input", "app.repositories", "sqlalchemy"))
    assert "plan_execution_service.execute(" in source and "runtime.resume(" in source
