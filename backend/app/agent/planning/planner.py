import hashlib

from pydantic import ValidationError

from app.agent.context.contracts import ResolvedContext
from app.agent.intents import BUSINESS_INTENTS, INTENT_TO_ALLOWED_RUNTIME_ACTIONS
from app.agent.planning.input_builders import WorkflowInputMissing, build_workflow_input
from app.agent.schemas.execution import RuntimeAction
from app.agent.schemas.planning import ExecutionPlan, PlanStatus, PlanStep
from app.agent.schemas.semantic import Intent, TaskSemanticFrame
from app.agent.skills.registry import INTENT_TO_SKILL, get_skill
from app.agent.workflows.definitions import WorkflowId
from app.agent.workflows.implementation_registry import WORKFLOW_HANDLER_REGISTRY
from app.agent.workflows.registry import get_workflow
from app.runtime.workflow_contract_registry import get_runtime_contract


class DeterministicPlanner:
    """仅消费 Semantic + Resolved Context 的确定性 Planner。"""

    def __init__(self, *, now=None):
        self.now = now

    def plan(self, frame: TaskSemanticFrame, context: ResolvedContext) -> ExecutionPlan:
        action = self._action(frame.primary_intent)
        plan_id = self._plan_id(frame, context)
        blocking = list(dict.fromkeys(context.blocking_missing_info))
        if frame.primary_intent == Intent.UNKNOWN or blocking or context.unresolved_references or context.ambiguous_references:
            semantic_missing = frame.missing_info if frame.primary_intent == Intent.UNKNOWN else []
            return ExecutionPlan(plan_id=plan_id, primary_intent=frame.primary_intent, action=action, missing_inputs=blocking or semantic_missing or ["需要澄清引用或目标"], status=PlanStatus.NEED_USER_INPUT)
        intents = [frame.primary_intent, *frame.sub_goals]
        if any(intent not in BUSINESS_INTENTS for intent in intents):
            if frame.primary_intent not in BUSINESS_INTENTS:
                return ExecutionPlan(plan_id=plan_id, primary_intent=frame.primary_intent, action=action, status=PlanStatus.READY)
            return ExecutionPlan(plan_id=plan_id, primary_intent=frame.primary_intent, action=action, missing_inputs=["多目标包含非 Workflow Intent"], status=PlanStatus.UNSUPPORTED)
        steps, missing = [], []
        for index, intent in enumerate(intents, start=1):
            skill_id = INTENT_TO_SKILL[intent]
            skill = get_skill(skill_id)
            workflow_id = WorkflowId(skill.workflow_id)
            workflow = get_workflow(workflow_id)
            try:
                typed_input = build_workflow_input(workflow_id, frame, context, self.now)
                get_runtime_contract(workflow_id).input_type.model_validate(typed_input)
            except (WorkflowInputMissing, ValidationError, ValueError) as exc:
                missing.extend(exc.fields if isinstance(exc, WorkflowInputMissing) else [str(exc)])
                continue
            step_id = f"step_{index}"
            steps.append(PlanStep(step_id=step_id, skill_id=skill_id.value, workflow_id=workflow.id.value, depends_on=[] if index == 1 else [f"step_{index - 1}"], reason=f"用户明确要求 {intent.value}", workflow_input=typed_input.model_dump(mode="json")))
        if missing or len(steps) != len(intents):
            return ExecutionPlan(plan_id=plan_id, primary_intent=frame.primary_intent, action=RuntimeAction.CLARIFY, steps=steps, missing_inputs=list(dict.fromkeys(missing)), status=PlanStatus.NEED_USER_INPUT)
        try:
            self._validate(steps, intents)
        except ValueError as exc:
            return ExecutionPlan(plan_id=plan_id, primary_intent=frame.primary_intent, action=action, missing_inputs=[str(exc)], status=PlanStatus.UNSUPPORTED)
        return ExecutionPlan(plan_id=plan_id, primary_intent=frame.primary_intent, action=action, steps=steps, required_inputs=[field for step in steps for field in (step.workflow_input or {})], status=PlanStatus.READY)

    @staticmethod
    def _action(intent):
        allowed = INTENT_TO_ALLOWED_RUNTIME_ACTIONS[intent]
        if intent in BUSINESS_INTENTS:
            return RuntimeAction.EXECUTE_PLAN
        priorities = (RuntimeAction.RESPOND, RuntimeAction.QUERY, RuntimeAction.CONFIRM, RuntimeAction.CANCEL, RuntimeAction.CLARIFY, RuntimeAction.EXECUTE_CONFIRMED_COMMAND)
        return next(action for action in priorities if action in allowed)

    @staticmethod
    def _validate(steps, intents):
        seen = set()
        for step, intent in zip(steps, intents, strict=True):
            if any(dep not in seen for dep in step.depends_on):
                raise ValueError("Plan dependency 无效或成环")
            skill = get_skill(step.skill_id)
            workflow = get_workflow(step.workflow_id)
            if INTENT_TO_SKILL[intent] != skill.id or workflow.skill_id != skill.id or workflow.id not in WORKFLOW_HANDLER_REGISTRY:
                raise ValueError("Registry mapping 不一致或 Workflow 未实现")
            get_runtime_contract(workflow.id).input_type.model_validate(step.workflow_input)
            seen.add(step.step_id)

    @staticmethod
    def _plan_id(frame, context):
        payload = frame.model_dump_json() + context.model_dump_json()
        return f"plan_{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]}"
