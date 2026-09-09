from app.agent.runtime import AgentRuntime
from app.schemas.agent import WorkflowRunRequest, WorkflowStepSpec


class ContentExperimentWorkflow:
    """内容实验 Agent 示例工作流。"""

    workflow_name = "ContentExperimentWorkflow"

    def __init__(self, runtime: AgentRuntime):
        """初始化内容实验工作流。"""
        self.runtime = runtime

    def run(self, account_id: int, experiment_payload: dict) -> object:
        """执行账号读取、竞品读取和候选实验创建。"""
        request = WorkflowRunRequest(
            workflow_name=self.workflow_name,
            account_id=account_id,
            input_payload={"account_id": account_id, "experiment_payload": experiment_payload},
            steps=[
                WorkflowStepSpec(tool_name="get_account_profile", payload={"account_id": account_id}),
                WorkflowStepSpec(tool_name="list_competitor_notes", payload={"account_id": account_id}),
                WorkflowStepSpec(tool_name="create_content_experiment", payload={"account_id": account_id, **experiment_payload}),
            ],
            max_steps=6,
            max_retry=1,
        )
        return self.runtime.run(request)
