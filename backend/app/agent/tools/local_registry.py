from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.agent.tools.base import ToolDefinition, ToolResult
from app.enums.agent import ToolType
from app.models.content_experiment import ContentExperiment
from app.repositories.account_repo import AccountProfileRepository
from app.repositories.agent_run_repo import AgentRunRepository
from app.repositories.content_draft_v2_repo import ContentDraftV2Repository
from app.repositories.crawler_collection_repo import CrawlerCollectionRepository
from app.repositories.post_publish_repo import PostPublishRepository
from app.schemas.confirmation import ConfirmationTaskCreate
from app.schemas.content_draft_v2 import ContentDraftV2Create
from app.schemas.provider_status import DataStatus, ProviderErrorCode
from app.schemas.post_publish import CollectMetricsRequest, ReviewCreate
from app.services.confirmation_sev import ConfirmationService
from app.services.content_draft_v2_sev import ContentDraftV2Service
from app.services.post_publish_sev import PostPublishService


class LocalToolRegistry:
    """核心业务能力的本地工具注册表。"""

    def __init__(self, db: Session):
        """初始化本地工具注册表。"""
        self.db = db
        self.tools = self._build_tools()

    def get_tool(self, tool_name: str) -> ToolDefinition | None:
        """按名称获取本地工具。"""
        return self.tools.get(tool_name)

    def list_tools(self) -> list[ToolDefinition]:
        """列出全部本地工具。"""
        return list(self.tools.values())

    def _build_tools(self) -> dict[str, ToolDefinition]:
        """构造本地工具映射。"""
        handlers = {
            "get_account_profile": self._get_account_profile,
            "list_competitor_notes": self._list_competitor_notes,
            "create_content_experiment": self._create_content_experiment,
            "save_content_draft": self._save_content_draft,
            "create_confirmation_task": self._create_confirmation_task,
            "save_metric_snapshot": self._save_metric_snapshot,
            "generate_review_report": self._generate_review_report,
            "save_strategy_memory": self._save_strategy_memory,
            "retrieve_strategy_memory": self._retrieve_strategy_memory,
        }
        confirmation_tools = {"create_confirmation_task"}
        return {
            name: ToolDefinition(
                name=name,
                tool_type=ToolType.LOCAL.value,
                handler=handler,
                description=f"{name} 本地业务工具",
                risk_level="MEDIUM" if name in confirmation_tools else "LOW",
                requires_confirmation=False,
                fallback_tool_name=self._fallback_name(name),
            )
            for name, handler in handlers.items()
        }

    def _get_account_profile(self, payload: dict) -> ToolResult:
        """查询账号画像。"""
        account = AccountProfileRepository(self.db).get_by_id(int(payload["account_id"]))
        if not account:
            return ToolResult(False, "get_account_profile", error="Account profile does not exist")
        return ToolResult(True, "get_account_profile", self._snapshot(account))

    def _list_competitor_notes(self, payload: dict) -> ToolResult:
        """查询竞品笔记快照。"""
        notes = CrawlerCollectionRepository(self.db).list_competitor_notes(int(payload["account_id"]))
        if not notes:
            return ToolResult(
                False,
                "list_competitor_notes",
                {
                    "count": 0,
                    "notes": [],
                    "data_quality": "EMPTY",
                    "reason": "NO_COMPETITOR_NOTES",
                    "error_code": ProviderErrorCode.COLLECTION_FAILED.value,
                    "data_status": DataStatus.NOT_PROVIDED.value,
                    "can_continue": False,
                    "action": "COLLECT_COMPETITOR_NOTES",
                    "hint": "当前账号暂无竞品笔记，请先通过 MCP 采集或手动录入真实样本后再做竞品分析。",
                    "suggestion": "请先通过 MCP 采集或手动录入 10-30 条真实公开笔记样本。",
                },
                error=ProviderErrorCode.COLLECTION_FAILED.value,
                metadata={
                    "business_state": True,
                    "data_status": DataStatus.NOT_PROVIDED.value,
                    "mock_used": False,
                },
            )
        return ToolResult(
            True,
            "list_competitor_notes",
            {
                "count": len(notes),
                "notes": [self._snapshot(item) for item in notes],
                "data_status": DataStatus.REAL.value,
            },
            metadata={"mock_used": False},
        )

    def _create_content_experiment(self, payload: dict) -> ToolResult:
        """创建候选内容实验。"""
        experiment = PostPublishRepository(self.db).create_experiment(self._experiment_fields(payload))
        return ToolResult(True, "create_content_experiment", {"experiment_id": experiment.id, "status": experiment.status})

    def _save_content_draft(self, payload: dict) -> ToolResult:
        """保存或生成内容草稿。"""
        if payload.get("generate_from_experiment"):
            draft = ContentDraftV2Service(self.db).generate_draft(
                self._draft_request(payload),
                agent_run_id=payload.get("_agent_run_id"),
                agent_step_id=payload.get("_agent_step_id"),
            )
            return ToolResult(True, "save_content_draft", {"draft_id": draft.id, "status": draft.status, "version": draft.version})
        draft = ContentDraftV2Repository(self.db).create_draft(ContentDraftV2Create.model_validate(payload))
        return ToolResult(True, "save_content_draft", {"draft_id": draft.id, "status": draft.status, "version": draft.version})

    def _create_confirmation_task(self, payload: dict) -> ToolResult:
        """创建人工确认任务。"""
        task = ConfirmationService(self.db).create_task(ConfirmationTaskCreate.model_validate(payload))
        return ToolResult(True, "create_confirmation_task", {"confirmation_task_id": task.id, "status": task.status, "risk_level": task.risk_level})

    def _save_metric_snapshot(self, payload: dict) -> ToolResult:
        """保存公开指标快照。"""
        note_id = int(payload["published_note_id"])
        request = CollectMetricsRequest.model_validate(payload["metrics_request"])
        snapshot = PostPublishService(self.db).collect_public_metrics(note_id, request)
        return ToolResult(True, "save_metric_snapshot", {"snapshot_id": snapshot.id, "snapshot_window": snapshot.snapshot_window})

    def _generate_review_report(self, payload: dict) -> ToolResult:
        """生成发布后复盘报告。"""
        report = PostPublishService(self.db).create_review(ReviewCreate(published_note_id=int(payload["published_note_id"])))
        return ToolResult(True, "generate_review_report", {"review_report_id": report.id, "result_status": report.result_status})

    def _save_strategy_memory(self, payload: dict) -> ToolResult:
        """保存策略记忆。"""
        response = PostPublishService(self.db).extract_memories(int(payload["review_report_id"]))
        return ToolResult(True, "save_strategy_memory", {"count": response.count, "memory_ids": [item.id for item in response.memories]})

    def _retrieve_strategy_memory(self, payload: dict) -> ToolResult:
        """检索并记录 Agent 使用的策略记忆。"""
        account_id = int(payload["account_id"])
        memories = PostPublishService(self.db).list_memories(account_id)
        selected = memories[: int(payload.get("limit", 3))]
        agent_run_id = payload.get("_agent_run_id")
        repo = AgentRunRepository(self.db)
        for memory in selected:
            if agent_run_id:
                repo.record_memory_usage(
                    {
                        "account_id": account_id,
                        "agent_run_id": int(agent_run_id),
                        "memory_id": memory.id,
                        "usage_reason": payload.get("usage_reason", "Agent selected candidate memory for workflow context."),
                        "usage_snapshot": memory.model_dump(mode="json"),
                    }
                )
        return ToolResult(
            True,
            "retrieve_strategy_memory",
            {"count": len(selected), "memory_ids": [memory.id for memory in selected], "memories": [memory.model_dump(mode="json") for memory in selected]},
        )

    def _fallback_name(self, tool_name: str) -> str | None:
        """获取本地工具的默认降级工具名。"""
        return {
            "list_competitor_notes": "collection_failed_fallback",
            "save_content_draft": "llm_output_failed_fallback",
            "generate_review_report": "comment_sample_insufficient_fallback",
        }.get(tool_name)

    def _experiment_fields(self, payload: dict) -> dict:
        """构造内容实验入库字段。"""
        return {
            "account_id": payload["account_id"],
            "analysis_report_id": payload.get("analysis_report_id"),
            "content_opportunity_id": payload.get("content_opportunity_id"),
            "experiment_name": payload.get("experiment_name", "Agent candidate experiment"),
            "hypothesis": payload.get("hypothesis", "Agent generated hypothesis"),
            "content_pillar": payload.get("content_pillar", "PROJECT"),
            "content_format": payload.get("content_format", "image note"),
            "main_variable": payload.get("main_variable", "topic_angle"),
            "control_variables": payload.get("control_variables", []),
            "primary_metric": payload.get("primary_metric", "collect"),
            "secondary_metrics": payload.get("secondary_metrics", ["comment", "lead"]),
            "success_criteria": payload.get("success_criteria", {"primary_metric": "collect"}),
            "failure_criteria": payload.get("failure_criteria", {"primary_metric": "collect"}),
            "fallback_strategy": payload.get("fallback_strategy", "Pause and return to opportunity analysis."),
            "risk_level": payload.get("risk_level", "LOW"),
            "target_metric": payload.get("target_metric", payload.get("primary_metric", "collect")),
            "expected_result": payload.get("expected_result", "collect_count >= 30"),
            "topic_angle": payload.get("topic_angle"),
            "selected_topic": payload.get("selected_topic"),
            "target_values": payload.get("target_values", {"collect_count": 30}),
            "source_type": "AGENT_TOOL",
            "status": "CANDIDATE",
        }

    def _draft_request(self, payload: dict):
        """构造草稿生成请求。"""
        from app.schemas.content_draft_v2 import GenerateDraftV2Request

        return GenerateDraftV2Request(experiment_id=int(payload["experiment_id"]), user_requirement=payload.get("user_requirement"))

    def _snapshot(self, obj) -> dict:
        """构造数据库对象快照。"""
        data = {key: value for key, value in vars(obj).items() if not key.startswith("_")}
        serializers = {
            Decimal: str,
            datetime: lambda value: value.isoformat(),
            date: lambda value: value.isoformat(),
        }
        return {key: self._serialize(value, serializers) for key, value in data.items()}

    def _serialize(self, value, serializers: dict) -> object:
        """序列化工具输出中的常见数据库类型。"""
        serializer = next((handler for value_type, handler in serializers.items() if isinstance(value, value_type)), None)
        return serializer(value) if serializer else value
