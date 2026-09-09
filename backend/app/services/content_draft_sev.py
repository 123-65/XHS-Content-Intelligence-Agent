from decimal import Decimal

from sqlalchemy.orm import Session

from app.llm.client import LLMClient
from app.models.content_draft import ContentDraft
from app.prompts.xhs_writer import XHS_WRITER_SYSTEM_PROMPT, build_xhs_writer_prompt
from app.repositories.content_draft_repo import ContentDraftRepository
from app.schemas.content_draft import ContentDraftCreate, DraftGenerateResult, GenerateDraftRequest, ImageScript


class ContentDraftService:
    """内容草稿业务服务。"""

    def __init__(self, db: Session):
        """初始化内容草稿服务。"""
        self.repo = ContentDraftRepository(db)

    def generate_draft(self, data: GenerateDraftRequest) -> ContentDraft:
        """生成并保存内容草稿。"""
        experiment = self._get_experiment_or_raise(data.experiment_id)
        account = self._get_account_or_raise(experiment.account_id)
        report = self.repo.get_analysis_report(experiment.analysis_report_id) if experiment.analysis_report_id else None
        generation_context = self._build_generation_context(account, experiment, report, data.user_requirement)

        draft_result, usage, estimated_cost, raw_response_id = self._generate_result(data.use_mock, generation_context, experiment)
        create_data = ContentDraftCreate(
            experiment_id=data.experiment_id,
            title=draft_result.title,
            body=draft_result.body,
            tags=draft_result.tags,
            cover_text=draft_result.cover_text,
            image_scripts=[item.model_dump() for item in draft_result.image_scripts],
            cta=draft_result.cta,
            version=self.repo.get_latest_version(data.experiment_id) + 1,
            generation_context=generation_context,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            estimated_cost=estimated_cost,
            raw_response_id=raw_response_id,
        )
        return self.repo.create(create_data)

    def list_drafts(self, experiment_id: int) -> list[ContentDraft]:
        """查询某个实验下的草稿列表。"""
        return self.repo.list_by_experiment(experiment_id)

    def get_draft(self, draft_id: int) -> ContentDraft:
        """查询草稿详情。"""
        draft = self.repo.get_by_id(draft_id)
        if draft:
            return draft
        raise ValueError("内容草稿不存在")

    def _generate_result(self, use_mock: bool, context: dict, experiment) -> tuple[DraftGenerateResult, dict, Decimal, str | None]:
        """生成草稿结果及模型用量信息。"""
        if use_mock:
            topic = experiment.selected_topic or experiment.experiment_name
            return self._mock_generate_result(topic), self._empty_usage(), Decimal("0"), None

        llm_result = self._generate_with_llm(context)
        return (
            llm_result.data,
            llm_result.usage.model_dump(),
            Decimal(str(llm_result.estimated_cost)),
            llm_result.raw_response_id,
        )

    def _generate_with_llm(self, context: dict):
        """调用 LLM 生成结构化内容草稿。"""
        client = LLMClient()
        return client.generate_structured(
            prompt=build_xhs_writer_prompt(context),
            schema_model=DraftGenerateResult,
            system_prompt=XHS_WRITER_SYSTEM_PROMPT,
            prompt_key="xhs_writer_draft_generation",
            prompt_version="v1",
        )

    def _build_generation_context(self, account, experiment, report, user_requirement: str | None) -> dict:
        """构建草稿生成上下文快照。"""
        return {
            "account": {
                "account_name": account.account_name,
                "positioning": account.positioning,
                "target_audience": account.target_audience,
                "business_model": account.business_model,
                "main_product": account.main_product,
                "lead_value": self._to_float(account.lead_value),
                "avg_order_value": self._to_float(account.avg_order_value),
                "gross_profit": self._to_float(account.gross_profit),
                "primary_goal": account.primary_goal,
                "tone_preference": account.tone_preference,
                "forbidden_topics": account.forbidden_topics,
            },
            "experiment": {
                "experiment_name": experiment.experiment_name,
                "hypothesis": experiment.hypothesis,
                "target_metric": experiment.target_metric,
                "expected_result": experiment.expected_result,
                "topic_angle": experiment.topic_angle,
                "selected_topic": experiment.selected_topic,
                "target_values": experiment.target_values,
            },
            "analysis_report": {
                "summary": getattr(report, "summary", None),
                "top_tags": getattr(report, "top_tags", []),
                "title_patterns": getattr(report, "title_patterns", []),
                "content_insights": getattr(report, "content_insights", []),
                "suggestions": getattr(report, "suggestions", []),
            },
            "user_requirement": user_requirement,
        }

    def _mock_generate_result(self, topic: str) -> DraftGenerateResult:
        """生成模拟草稿，用于开发阶段联调。"""
        return DraftGenerateResult(
            title=f"普通大学生做 {topic}，别一上来就学复杂框架",
            body=(
                "很多人学 AI Agent，一开始就冲复杂框架，结果越学越乱。\n\n"
                "如果你是普通大学生，或者基础一般，建议先把顺序反过来：先理解 API 调用，再做工具调用，"
                "再做一个能跑通业务闭环的小项目。\n\n"
                "真正能写进简历的不是“我会某个框架”，而是你能讲清楚：业务问题是什么、数据怎么流动、"
                "模型在哪个环节发挥作用、失败时怎么兜底、成本怎么控制。"
            ),
            tags=["AI学习", "AI Agent", "项目实战", "大学生求职", "后端开发"],
            cover_text="AI Agent 项目别乱学，先按这个顺序做",
            image_scripts=[
                ImageScript(index=1, title="别一上来学框架", content="先搞懂 API、工具调用、业务流程，再看复杂框架。", visual_hint="封面大字，突出学习顺序"),
                ImageScript(index=2, title="第一步：API 调用", content="先会调用模型，理解 prompt、输入输出、结构化返回。", visual_hint="流程图"),
                ImageScript(index=3, title="第二步：工具调用", content="让 AI 能调用搜索、数据库、文件、爬虫等工具。", visual_hint="模块连接图"),
                ImageScript(index=4, title="第三步：业务闭环", content="不要只做聊天框，要做采集、分析、生成、复盘、策略更新。", visual_hint="闭环箭头图"),
                ImageScript(index=5, title="怎么写进简历", content="重点写工程化：LLMClient、Prompt 协议、日志、成本、失败兜底。", visual_hint="简历亮点清单"),
            ],
            cta="你可以先收藏这套顺序。想看完整项目拆解的话，可以评论区告诉我你现在做到哪一步。",
        )

    def _get_experiment_or_raise(self, experiment_id: int):
        """查询内容实验，不存在时抛出业务错误。"""
        experiment = self.repo.get_experiment(experiment_id)
        if experiment:
            return experiment
        raise ValueError("内容实验不存在")

    def _get_account_or_raise(self, account_id: int):
        """查询账号配置，不存在时抛出业务错误。"""
        account = self.repo.get_account(account_id)
        if account:
            return account
        raise ValueError("账号配置不存在")

    def _empty_usage(self) -> dict:
        """返回空模型用量。"""
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    def _to_float(self, value) -> float:
        """将数值转成 JSONB 友好的 float。"""
        return float(value or 0)
