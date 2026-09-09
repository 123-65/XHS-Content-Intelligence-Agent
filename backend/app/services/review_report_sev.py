from decimal import Decimal

from sqlalchemy.orm import Session

from app.llm.client import LLMClient
from app.models.review_report import ReviewReport
from app.prompts.content_reviewer import CONTENT_REVIEWER_SYSTEM_PROMPT, build_content_reviewer_prompt
from app.repositories.review_report_repo import ReviewReportRepository
from app.schemas.review_report import DraftReviewResult, ReviewDraftRequest, ReviewIssue, ReviewReportCreate


class ReviewReportService:
    """内容审核业务服务。"""

    def __init__(self, db: Session):
        """初始化内容审核服务。"""
        self.repo = ReviewReportRepository(db)

    def review_draft(self, data: ReviewDraftRequest) -> ReviewReport:
        """审核内容草稿并保存审核报告。"""
        draft = self._get_draft_or_raise(data.draft_id)
        experiment = self._get_experiment_or_raise(draft.experiment_id)
        account = self._get_account_or_raise(experiment.account_id)
        context = self._build_review_context(account, experiment, draft)

        review_result, usage, estimated_cost, raw_response_id = self._review_result(data.use_mock, context, draft)
        create_data = ReviewReportCreate(
            draft_id=draft.id,
            passed=review_result.passed,
            score=review_result.score,
            quality_score=review_result.quality_score,
            conversion_score=review_result.conversion_score,
            evidence_usage_score=review_result.evidence_usage_score,
            risk_level=review_result.risk_level,
            issues=[item.model_dump() for item in review_result.issues],
            suggestions=review_result.suggestions,
            summary=review_result.summary,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            estimated_cost=estimated_cost,
            raw_response_id=raw_response_id,
        )
        report = self.repo.create(create_data)
        self.repo.update_draft_status(draft, "REVIEW_PASSED" if report.passed else "REVIEW_FAILED")
        return report

    def get_report(self, report_id: int) -> ReviewReport:
        """查询审核报告详情。"""
        report = self.repo.get_by_id(report_id)
        if report:
            return report
        raise ValueError("审核报告不存在")

    def list_reports_by_draft(self, draft_id: int) -> list[ReviewReport]:
        """查询草稿审核报告列表。"""
        return self.repo.list_by_draft(draft_id)

    def _review_result(self, use_mock: bool, context: dict, draft) -> tuple[DraftReviewResult, dict, Decimal, str | None]:
        """生成审核结果及模型用量信息。"""
        if use_mock:
            return self._mock_review_result(draft), self._empty_usage(), Decimal("0"), None

        llm_result = self._review_with_llm(context)
        return (
            llm_result.data,
            llm_result.usage.model_dump(),
            Decimal(str(llm_result.estimated_cost)),
            llm_result.raw_response_id,
        )

    def _review_with_llm(self, context: dict):
        """调用 LLM 审核内容草稿。"""
        client = LLMClient()
        return client.generate_structured(
            prompt=build_content_reviewer_prompt(context),
            schema_model=DraftReviewResult,
            system_prompt=CONTENT_REVIEWER_SYSTEM_PROMPT,
            prompt_key="content_reviewer",
            prompt_version="v1",
        )

    def _build_review_context(self, account, experiment, draft) -> dict:
        """构建审核上下文。"""
        return {
            "account": {
                "account_name": account.account_name,
                "positioning": account.positioning,
                "target_audience": account.target_audience,
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
            "draft": {
                "title": draft.title,
                "body": draft.body,
                "tags": draft.tags,
                "cover_text": draft.cover_text,
                "image_scripts": draft.image_scripts,
                "cta": draft.cta,
                "generation_context": draft.generation_context,
            },
        }

    def _mock_review_result(self, draft) -> DraftReviewResult:
        """生成模拟审核结果，用于开发阶段联调。"""
        issues = [
            ReviewIssue(field="title", level="MEDIUM", message="标题略长，小红书展示时可能不够聚焦。")
        ] if len(draft.title) > 30 else []
        issues.extend(self._missing_cta_issues(draft))
        issues.extend(self._image_script_issues(draft))

        suggestions = [
            *self._title_suggestions(draft),
            *self._cta_suggestions(draft),
            *self._image_script_suggestions(draft),
            "正文可以继续增加一个具体例子，让用户更容易代入。",
            "可以在封面文案里突出“学习顺序”或“项目路线”，提高收藏动机。",
        ]

        passed = not any(item.level == "HIGH" for item in issues)
        return DraftReviewResult(
            passed=passed,
            score=82 if passed else 68,
            quality_score=84,
            conversion_score=78 if draft.cta else 55,
            evidence_usage_score=75,
            risk_level="MEDIUM" if issues else "LOW",
            issues=issues,
            suggestions=suggestions,
            summary="这篇草稿整体符合学习类账号定位，适合目标用户，但标题可以更聚焦，正文还可以增加具体案例。",
        )

    def _get_draft_or_raise(self, draft_id: int):
        """查询草稿，不存在时抛出业务错误。"""
        draft = self.repo.get_draft(draft_id)
        if draft:
            return draft
        raise ValueError("内容草稿不存在")

    def _get_experiment_or_raise(self, experiment_id: int):
        """查询内容实验，不存在时抛出业务错误。"""
        experiment = self.repo.get_experiment(experiment_id)
        if experiment:
            return experiment
        raise ValueError("内容实验不存在")

    def _get_account_or_raise(self, account_id: int):
        """查询账号，不存在时抛出业务错误。"""
        account = self.repo.get_account(account_id)
        if account:
            return account
        raise ValueError("账号配置不存在")

    def _missing_cta_issues(self, draft) -> list[ReviewIssue]:
        """返回 CTA 缺失问题。"""
        return [
            ReviewIssue(field="cta", level="HIGH", message="缺少明确 CTA，不利于引导收藏、评论或私信。")
        ] if not draft.cta else []

    def _image_script_issues(self, draft) -> list[ReviewIssue]:
        """返回图片脚本问题。"""
        return [
            ReviewIssue(field="image_scripts", level="MEDIUM", message="图片脚本数量偏少，不符合小红书图文内容的信息承载习惯。")
        ] if not draft.image_scripts or len(draft.image_scripts) < 3 else []

    def _title_suggestions(self, draft) -> list[str]:
        """返回标题建议。"""
        return ["标题可以压缩到 20 到 28 字，突出一个核心痛点。"] if len(draft.title) > 30 else []

    def _cta_suggestions(self, draft) -> list[str]:
        """返回 CTA 建议。"""
        return ["建议增加自然 CTA，例如引导用户评论当前学习阶段。"] if not draft.cta else []

    def _image_script_suggestions(self, draft) -> list[str]:
        """返回图片脚本建议。"""
        return ["建议补充 4 到 6 张图片脚本，形成完整阅读节奏。"] if not draft.image_scripts or len(draft.image_scripts) < 3 else []

    def _empty_usage(self) -> dict:
        """返回空模型用量。"""
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
