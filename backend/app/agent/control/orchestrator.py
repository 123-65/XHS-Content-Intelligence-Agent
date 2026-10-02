from urllib.parse import urlparse

from app.agent.context.contracts import ContextResolverInput, CurrentTurnMaterialCandidate, CurrentTurnMaterialType, ObjectRef, OpportunityCollection, ResolvedObjectType, StructuredContext, TrustedContextRef
from app.agent.control.resume_builders import build_resume_input
from app.agent.control.turn_contracts import AgentTurnInput
from app.agent.schemas.execution import AgentTurnResult, ArtifactRef, ArtifactType, RuntimeAction, WorkflowStatus
from app.agent.schemas.interaction import PendingInteraction, PendingInteractionType
from app.agent.schemas.planning import PlanStatus
from app.agent.schemas.semantic import Intent, SemanticReferenceType
from app.agent.workflows.definitions import WorkflowId
from app.runtime.workflow_resume import WorkflowResumeRequest


WORKFLOW_INTENTS = {
    WorkflowId.RESEARCH_V1: Intent.RESEARCH,
    WorkflowId.CONTENT_STRATEGY_V1: Intent.CONTENT_STRATEGY,
    WorkflowId.CONTENT_CREATION_V1: Intent.CONTENT_CREATE,
    WorkflowId.CONTENT_REFINEMENT_V1: Intent.CONTENT_REFINE,
    WorkflowId.POST_PUBLISH_REVIEW_V1: Intent.POST_PUBLISH_REVIEW,
}
INDEPENDENT_PENDING_INTENTS = {Intent.GENERAL_CHAT, Intent.QUERY_PROFILE, Intent.QUERY_HISTORY, Intent.UPDATE_PROFILE, Intent.UPDATE_STRATEGY, Intent.CANCEL_TASK}


class AgentTurnOrchestrator:
    """统一组织一次 Turn；Workflow 只经 PlanExecutionService / AgentRuntime。"""

    def __init__(self, *, semantic_layer, context_resolver, planner, plan_execution_service, runtime, context_owner, action_handlers=None):
        self.semantic_layer = semantic_layer
        self.context_resolver = context_resolver
        self.planner = planner
        self.plan_execution_service = plan_execution_service
        self.runtime = runtime
        self.context_owner = context_owner
        self.action_handlers = action_handlers or {}

    def handle_turn(self, turn: AgentTurnInput, execution_context, *, workspace_selection=None) -> AgentTurnResult:
        state = self.context_owner.load(turn.conversation_id, turn.account_ref)
        frame = self.semantic_layer.understand(self._semantic_turn_text(turn))
        authoritative_note_urls = self._authoritative_current_turn_note_urls(turn, execution_context)
        frame = frame.model_copy(update={
            # Server-authorized structured Note materials are the current Turn's
            # external-material authority. Semantic reconstruction remains useful
            # only when this Turn did not submit authoritative Note materials.
            "note_urls": authoritative_note_urls or frame.note_urls,
            # Structured current-turn Profile materials are authoritative. The semantic
            # layer only sees their count, so its reconstructed values cannot expand
            # the server-authorized collection scope.
            "profile_urls": list(dict.fromkeys(turn.profile_urls or frame.profile_urls)),
        })
        frame = self._resume_preworkflow_research_material(frame, turn, state)
        frame = self._exclude_external_material_references(frame, turn)
        resolved = self.context_resolver.resolve(ContextResolverInput(
            account_ref=turn.account_ref,
            semantic_frame=frame,
            current_turn_materials=self._current_turn_materials(turn, execution_context),
            workspace_selection=workspace_selection or StructuredContext(),
            pending_context=state.recent_context if state.active_pending_run_ref else None,
            conversation_context=state.recent_context,
        ))
        if state.active_pending_run_ref and frame.primary_intent not in INDEPENDENT_PENDING_INTENTS:
            resumed = self._maybe_resume(turn, frame, resolved, state, execution_context)
            if resumed is not None:
                return resumed

        plan = self.planner.plan(frame, resolved)
        if plan.status == PlanStatus.NEED_USER_INPUT:
            pending = self._clarification(plan.missing_inputs or resolved.blocking_missing_info)
            if frame.primary_intent == Intent.RESEARCH and "research_material" in pending.required_fields:
                state.active_pending_interaction = pending
                state.active_pending_semantic_frame = frame
                self.context_owner.save(turn.conversation_id, turn.account_ref, state)
            return AgentTurnResult(action=RuntimeAction.CLARIFY, intent=frame.primary_intent, message=pending.reason, pending_interaction=pending, status=WorkflowStatus.WAITING_USER)
        if plan.status == PlanStatus.UNSUPPORTED:
            return AgentTurnResult(action=plan.action, intent=frame.primary_intent, message="当前请求暂不支持安全执行。", warnings=plan.missing_inputs, status=WorkflowStatus.FAILED)
        if plan.action != RuntimeAction.EXECUTE_PLAN:
            return self._handle_control(turn, frame, plan.action)

        execution = self.plan_execution_service.execute(plan, execution_context)
        if not execution.step_results:
            return AgentTurnResult(action=RuntimeAction.CLARIFY, intent=frame.primary_intent, message="当前计划没有可执行步骤。", status=WorkflowStatus.WAITING_USER)
        last = execution.step_results[-1]
        self._apply_runtime_results(turn, state, plan, execution.step_results)
        self.context_owner.save(turn.conversation_id, turn.account_ref, state)
        return AgentTurnResult(
            action=RuntimeAction.EXECUTE_PLAN, intent=frame.primary_intent, run_ref=last.run_ref,
            checkpoint_version=last.checkpoint_version, message=self._runtime_message(last.status, last.pending_interaction),
            artifacts=self._artifacts(execution.step_results), pending_interaction=last.pending_interaction,
            result=last.result, error=last.error, status=last.status,
        )

    def _maybe_resume(self, turn, frame, resolved, state, execution_context):
        current = self.runtime.get_run(state.active_pending_run_ref)
        if current.account_ref != turn.account_ref or current.status != WorkflowStatus.WAITING_USER or current.pending_interaction is None:
            self._clear_pending(state)
            self.context_owner.save(turn.conversation_id, turn.account_ref, state)
            return None
        workflow = WorkflowId(current.workflow_name)
        if frame.primary_intent not in {Intent.UNKNOWN, WORKFLOW_INTENTS[workflow]}:
            return None
        if frame.primary_intent == Intent.UNKNOWN and not self._has_pending_answer(frame, resolved):
            return None
        new_input = build_resume_input(workflow, frame, resolved, current.pending_interaction)
        result = self.runtime.resume(WorkflowResumeRequest(run_ref=current.run_ref, expected_checkpoint_version=current.checkpoint_version, new_input=new_input), execution_context)
        if result.status == WorkflowStatus.WAITING_USER:
            state.active_pending_run_ref = result.run_ref
            state.active_pending_checkpoint_version = result.checkpoint_version
            state.active_pending_interaction = result.pending_interaction
        else:
            self._clear_pending(state)
            self._update_recent(state, result.result, turn.account_ref)
        self.context_owner.save(turn.conversation_id, turn.account_ref, state)
        return AgentTurnResult(
            action=RuntimeAction.EXECUTE_PLAN, intent=frame.primary_intent, run_ref=result.run_ref,
            checkpoint_version=result.checkpoint_version, message=self._runtime_message(result.status, result.pending_interaction),
            artifacts=self._artifacts_from_payload(result.result), pending_interaction=result.pending_interaction,
            result=result.result, warnings=result.warnings, error=result.error, status=result.status,
        )

    def _handle_control(self, turn, frame, action):
        handler = self.action_handlers.get(frame.primary_intent)
        if action == RuntimeAction.RESPOND:
            message = handler(turn, frame) if handler else "你好，我可以帮你研究、策划、创作和优化小红书内容。"
            return AgentTurnResult(action=action, intent=frame.primary_intent, message=message, status=WorkflowStatus.SUCCESS)
        if action == RuntimeAction.QUERY:
            if handler:
                value = handler(turn, frame)
                message, result = value if isinstance(value, tuple) else (str(value), value)
                return AgentTurnResult(action=action, intent=frame.primary_intent, message=message, result=result, status=WorkflowStatus.SUCCESS)
            return AgentTurnResult(action=action, intent=frame.primary_intent, message="该查询尚未接入正式 Control Query Handler。", warnings=["CONTROL_QUERY_HANDLER_UNAVAILABLE"], status=WorkflowStatus.FAILED)
        if action == RuntimeAction.CONFIRM:
            pending = PendingInteraction(type=PendingInteractionType.CONFIRMATION, reason=frame.primary_goal or "请确认是否执行该更新。", required_fields=["confirmation"], resume_token="CONTROL_COMMAND_CONFIRMATION")
            return AgentTurnResult(action=action, intent=frame.primary_intent, message=pending.reason, pending_interaction=pending, status=WorkflowStatus.WAITING_USER)
        if action == RuntimeAction.CANCEL:
            return AgentTurnResult(action=action, intent=frame.primary_intent, message="已识别取消请求；当前 Runtime 尚无正式 cancel capability，未修改运行状态。", warnings=["RUNTIME_CANCEL_CAPABILITY_UNAVAILABLE"], status=WorkflowStatus.PENDING)
        return AgentTurnResult(action=action, intent=frame.primary_intent, message="该控制动作尚未接入正式执行器。", warnings=["CONTROL_COMMAND_EXECUTOR_UNAVAILABLE"], status=WorkflowStatus.PENDING)

    def _apply_runtime_results(self, turn, state, plan, results):
        last = results[-1]
        if last.status == WorkflowStatus.WAITING_USER:
            state.active_pending_run_ref, state.active_pending_checkpoint_version = last.run_ref, last.checkpoint_version
            state.active_pending_interaction = last.pending_interaction
            state.active_pending_semantic_frame = None
            return
        self._clear_pending(state)
        for step, result in zip(plan.steps, results, strict=False):
            if result.status in {WorkflowStatus.SUCCESS, WorkflowStatus.PARTIAL_SUCCESS}:
                self._update_recent(state, result.result, turn.account_ref)

    @staticmethod
    def _update_recent(state, payload, account_ref):
        if payload is None: return
        data = payload.model_dump(mode="json") if hasattr(payload, "model_dump") else dict(payload)
        refs = list(state.recent_context.references)
        def add(kind, value):
            if isinstance(value, dict): value = value.get("id")
            if value is None: return
            item = TrustedContextRef(ref=ObjectRef(type=kind, id=value), account_ref=account_ref)
            if item.ref not in [existing.ref for existing in refs]: refs.append(item)
        add(ResolvedObjectType.RESEARCH, data.get("research_artifact_ref"))
        add(ResolvedObjectType.CONTENT_STRATEGY, data.get("strategy_artifact_ref"))
        add(ResolvedObjectType.DRAFT, data.get("draft_ref"))
        generated, strategy = data.get("generated_opportunity_refs") or [], data.get("strategy_artifact_ref")
        if isinstance(strategy, dict): strategy = strategy.get("id")
        if generated and strategy:
            strategy_ref = TrustedContextRef(ref=ObjectRef(type=ResolvedObjectType.CONTENT_STRATEGY, id=strategy), account_ref=account_ref)
            opportunities = [TrustedContextRef(ref=ObjectRef(type=ResolvedObjectType.CONTENT_OPPORTUNITY, id=item), account_ref=account_ref) for item in generated]
            state.recent_context.opportunity_collections = [*state.recent_context.opportunity_collections, OpportunityCollection(strategy_ref=strategy_ref, opportunity_refs=opportunities)][-5:]
        state.recent_context.references = refs[-20:]

    @classmethod
    def _artifacts(cls, results):
        return [artifact for item in results for artifact in cls._artifacts_from_payload(item.result)]

    @staticmethod
    def _artifacts_from_payload(payload):
        if payload is None: return []
        data = payload.model_dump(mode="json") if hasattr(payload, "model_dump") else dict(payload)
        mapping = {"research_artifact_ref": ArtifactType.RESEARCH, "strategy_artifact_ref": ArtifactType.CONTENT_STRATEGY, "draft_ref": ArtifactType.DRAFT, "review_artifact_ref": ArtifactType.POST_PUBLISH_REVIEW}
        artifacts = []
        for key, kind in mapping.items():
            value = data.get(key)
            if isinstance(value, dict): value = value.get("id")
            if isinstance(value, int): artifacts.append(ArtifactRef(type=kind, id=value))
        return artifacts

    @staticmethod
    def _clear_pending(state):
        state.active_pending_run_ref = state.active_pending_checkpoint_version = state.active_pending_interaction = None
        state.active_pending_semantic_frame = None

    @staticmethod
    def _clarification(items):
        aliases = {
            "note_urls_or_profile_urls": "research_material",
            "note_urls": "research_material",
            "profile_urls": "research_material",
        }
        fields = list(dict.fromkeys(aliases.get(str(item), str(item)) for item in items if item)) or ["required_information"]
        reason = "请提供要分析的小红书账号或笔记链接。" if "research_material" in fields else "请补充完成任务所需的信息。"
        return PendingInteraction(type=PendingInteractionType.CLARIFICATION, reason=reason, required_fields=fields, resume_token="TURN_CLARIFICATION")

    @staticmethod
    def _has_pending_answer(frame, resolved):
        return bool(frame.note_urls or frame.profile_urls or frame.primary_goal or resolved.resolved_references) and frame.confidence >= .5

    @staticmethod
    def _semantic_turn_text(turn):
        """Tell semantic parsing that structured materials exist without reinterpreting URLs."""
        if not turn.note_urls and not turn.profile_urls:
            return turn.text
        semantic_text = turn.text
        for value in turn.note_urls:
            semantic_text = semantic_text.replace(value, "[XHS_NOTE_URL]")
        for value in turn.profile_urls:
            semantic_text = semantic_text.replace(value, "[XHS_PROFILE_URL]")
        return (
            f"{semantic_text}\n\n"
            "本轮请求的结构化字段已提供用户授权的公开材料："
            f"note_urls={len(turn.note_urls)} 条，profile_urls={len(turn.profile_urls)} 条。"
            "这些材料不是自然语言引用；不要把 URL 解析为 references，也不要报告缺少 URL。"
        )

    @staticmethod
    def _current_turn_materials(turn, execution_context):
        """Build ephemeral candidates only from the server-authorized current request scope."""
        scope = getattr(execution_context, "collection_access_scope", None)
        if scope is None or scope.workspace_account_ref != turn.account_ref or str(scope.authorization_source) != "USER_PROVIDED":
            return []
        allowed_profiles = set(scope.allowed_profile_urls)
        allowed_notes = set(scope.allowed_note_urls)
        candidates = []
        for value, material_type, allowed, prefix in (
            *((value, CurrentTurnMaterialType.PROFILE, allowed_profiles, "/user/profile/") for value in turn.profile_urls),
            *((value, CurrentTurnMaterialType.NOTE, allowed_notes, "/explore/") for value in turn.note_urls),
        ):
            if value not in allowed:
                continue
            parsed = urlparse(value.strip())
            host = (parsed.hostname or "").lower()
            if parsed.scheme not in {"http", "https"} or host not in {"xiaohongshu.com", "www.xiaohongshu.com"}:
                continue
            if not parsed.path.startswith(prefix) or not parsed.path.removeprefix(prefix):
                continue
            candidates.append(CurrentTurnMaterialCandidate(
                type=material_type,
                account_ref=turn.account_ref,
                source_url=value,
                external_identity=parsed.path.removeprefix(prefix).split("/", 1)[0],
            ))
        return candidates

    @staticmethod
    def _authoritative_current_turn_note_urls(turn, execution_context):
        """Return only Note URLs authorized for this exact current request."""
        scope = getattr(execution_context, "collection_access_scope", None)
        if scope is None or scope.workspace_account_ref != turn.account_ref or str(scope.authorization_source) != "USER_PROVIDED":
            return []
        allowed = set(scope.allowed_note_urls)
        return list(dict.fromkeys(value for value in turn.note_urls if value in allowed))

    @staticmethod
    def _exclude_external_material_references(frame, turn):
        """Keep current-Turn materials out of canonical reference resolution."""
        material_urls = tuple([*turn.note_urls, *turn.profile_urls])
        material_words = {"这篇", "这篇笔记", "这个链接", "这个账号", "该账号", "这个主页"}
        references = []
        for reference in frame.references:
            raw = reference.raw_text.strip()
            is_material = any(value and value in raw for value in material_urls)
            if frame.primary_intent == Intent.RESEARCH and reference.type in {
                SemanticReferenceType.PROFILE,
                SemanticReferenceType.ACCOUNT,
            }:
                is_material = True
            if material_urls and reference.type == SemanticReferenceType.UNKNOWN and raw in material_words:
                is_material = True
            if not is_material:
                references.append(reference)
        return frame.model_copy(update={"references": references})

    @staticmethod
    def _resume_preworkflow_research_material(frame, turn, state):
        """Fill a pre-Run Research clarification from a material-only follow-up Turn."""
        pending = state.active_pending_interaction
        pending_frame = state.active_pending_semantic_frame
        if (
            state.active_pending_run_ref
            or pending is None
            or pending_frame is None
            or "research_material" not in pending.required_fields
            or not (turn.note_urls or turn.profile_urls)
            or frame.primary_intent not in {Intent.UNKNOWN, Intent.RESEARCH}
        ):
            return frame
        return pending_frame.model_copy(update={
            "note_urls": list(turn.note_urls),
            "profile_urls": list(turn.profile_urls),
            "missing_info": [],
            "confidence": max(frame.confidence, pending_frame.confidence),
        })

    @staticmethod
    def _runtime_message(status, pending):
        if status == WorkflowStatus.WAITING_USER: return pending.reason if pending else "任务需要补充信息。"
        if status in {WorkflowStatus.SUCCESS, WorkflowStatus.PARTIAL_SUCCESS}: return "任务执行完成。"
        if status == WorkflowStatus.FAILED: return "任务执行失败。"
        return f"任务状态：{status.value}"
