from app.agent.schemas.execution import WorkflowStatus
from app.agent.schemas.planning import ExecutionPlan, PlanExecutionResult, PlanStatus, PlanStepExecution
from app.runtime.agent_runtime import AgentRuntime, WorkflowStartRequest


class PlanExecutionService:
    """READY Plan 到 AgentRuntime.start 的唯一薄适配层。"""

    def __init__(self, runtime: AgentRuntime):
        self.runtime = runtime

    def execute(self, plan: ExecutionPlan, execution_context) -> PlanExecutionResult:
        if plan.status != PlanStatus.READY or not plan.steps:
            return PlanExecutionResult(plan_id=plan.plan_id)
        completed = set()
        results = []
        for step in plan.steps:
            if not step.executable or not set(step.depends_on).issubset(completed):
                return PlanExecutionResult(plan_id=plan.plan_id, step_results=results, stopped_before_step=step.step_id, status=results[-1].status if results else None)
            runtime_result = self.runtime.start(WorkflowStartRequest(workflow_name=step.workflow_id, input=step.workflow_input or {}), execution_context)
            results.append(PlanStepExecution(step_id=step.step_id, run_ref=runtime_result.run_ref, checkpoint_version=getattr(runtime_result, "checkpoint_version", None), status=runtime_result.status, pending_interaction=runtime_result.pending_interaction, result=runtime_result.result, error=runtime_result.error))
            if runtime_result.status not in {WorkflowStatus.SUCCESS, WorkflowStatus.PARTIAL_SUCCESS}:
                next_step = plan.steps[len(results)].step_id if len(results) < len(plan.steps) else None
                return PlanExecutionResult(plan_id=plan.plan_id, step_results=results, stopped_before_step=next_step, status=runtime_result.status)
            completed.add(step.step_id)
        return PlanExecutionResult(plan_id=plan.plan_id, step_results=results, status=results[-1].status if results else None)
