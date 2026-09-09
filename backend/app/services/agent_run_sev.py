from sqlalchemy.orm import Session

from app.agent.observability import AgentObservabilityBuilder
from app.repositories.agent_run_repo import AgentRunRepository
from app.schemas.agent import AgentRunDetailResponse, AgentRunResponse, AgentStepResponse


class AgentRunService:
    """AgentRun 查询服务。"""

    def __init__(self, db: Session):
        """初始化 AgentRun 查询服务。"""
        self.repo = AgentRunRepository(db)
        self.observability = AgentObservabilityBuilder()

    def list_runs(self, account_id: int | None = None) -> list[AgentRunResponse]:
        """查询 AgentRun 列表。"""
        return [self.observability.build_run_response(item, self.repo.list_steps(item.id)) for item in self.repo.list_runs(account_id)]

    def get_run(self, agent_run_id: int) -> AgentRunDetailResponse:
        """查询 AgentRun 详情。"""
        run = self._get_run_or_raise(agent_run_id)
        return self.observability.build_detail_response(run, self.repo.list_steps(agent_run_id))

    def list_steps(self, agent_run_id: int) -> list[AgentStepResponse]:
        """查询 AgentRun 的步骤列表。"""
        self._get_run_or_raise(agent_run_id)
        return [self.observability.build_step_response(item) for item in self.repo.list_steps(agent_run_id)]

    def _get_run_or_raise(self, agent_run_id: int):
        """返回 AgentRun，不存在时抛出业务错误。"""
        run = self.repo.get_run(agent_run_id)
        if not run:
            raise ValueError("AgentRun does not exist")
        return run
