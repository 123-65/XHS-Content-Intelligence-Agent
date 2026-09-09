from sqlalchemy.orm import Session

from app.agent.observability import AgentObservabilityBuilder
from app.models.crawl_task import CrawlTask
from app.models.prompt_run_log import PromptRunLog
from app.repositories.agent_run_repo import AgentRunRepository


class DemoService:
    """可视化验收数据服务。"""

    def __init__(self, db: Session):
        """初始化可视化验收服务。"""
        self.db = db
        self.repo = AgentRunRepository(db)
        self.observability = AgentObservabilityBuilder()

    def latest_run(self) -> dict:
        """返回最近一次 AgentRun 的可视化验收摘要。"""
        run = self.repo.list_runs()[0] if self.repo.list_runs() else None
        steps = self.repo.list_steps(run.id) if run else []
        return {
            "llm_provider": self._latest_llm_provider(),
            "crawler_provider": self._latest_crawler_provider(),
            "run": self.observability.build_detail_response(run, steps).model_dump(mode="json") if run else None,
            "real_steps": [item.tool_name for item in steps if not self._step_is_mock(item)],
            "mock_or_fallback_steps": [item.tool_name for item in steps if self._step_is_mock(item) or item.status == "FALLBACK_USED"],
            "business_objects": self._business_objects(steps),
        }

    def latest_steps(self) -> list[dict]:
        """返回最近一次 AgentRun 的步骤可视化验收详情。"""
        runs = self.repo.list_runs()
        if not runs:
            return []
        return [self._visual_step(item) for item in self.repo.list_steps(runs[0].id)]

    def _visual_step(self, step) -> dict:
        """构造单步可视化验收信息。"""
        response = self.observability.build_step_response(step).model_dump(mode="json")
        metadata = (step.output_payload or {}).get("metadata") or {}
        return {
            "step_order": response["step_order"],
            "step_name": response["step_name"],
            "tool_name": step.tool_name,
            "used_real_data": not self._step_is_mock(step),
            "used_mock_or_fallback": self._step_is_mock(step) or response["fallback_used"],
            "input_summary": response["tool_input"],
            "output_summary": response["tool_output_summary"],
            "latency_ms": response["latency_ms"],
            "success": step.status in {"SUCCESS", "FALLBACK_USED"},
            "failure_reason": step.error_message,
            "provider": metadata.get("provider") or metadata.get("tool_name"),
        }

    def _latest_llm_provider(self) -> dict:
        """查询最近一次 LLM 调用 Provider。"""
        log = self.db.query(PromptRunLog).order_by(PromptRunLog.created_at.desc(), PromptRunLog.id.desc()).first()
        return {"provider": log.provider, "model": log.model, "is_mock": log.is_mock} if log else {}

    def _latest_crawler_provider(self) -> dict:
        """查询最近一次 Crawler 调用 Provider。"""
        task = self.db.query(CrawlTask).order_by(CrawlTask.created_at.desc(), CrawlTask.id.desc()).first()
        return {"provider": task.provider_name, "available": task.status == "SUCCESS"} if task else {}

    def _step_is_mock(self, step) -> bool:
        """判断步骤是否使用 Mock 或 fallback。"""
        output = step.output_payload or {}
        metadata = output.get("metadata") or {}
        data = output.get("data") or {}
        return bool(metadata.get("mock") or data.get("is_mock") or step.status == "FALLBACK_USED")

    def _business_objects(self, steps: list) -> list[dict]:
        """从步骤输出中提取最终生成的业务对象。"""
        objects = []
        for step in steps:
            data = (step.output_payload or {}).get("data") or {}
            objects.extend({"type": key.replace("_id", ""), "id": value} for key, value in data.items() if key.endswith("_id"))
        return objects
