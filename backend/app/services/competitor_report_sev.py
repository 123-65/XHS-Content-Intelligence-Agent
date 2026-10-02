from sqlalchemy.orm import Session

from app.analysis.competitor.assembler import CompetitorReportAssembler
from app.analysis.competitor.engine import CompetitorAnalysisEngine
from app.analysis.competitor.evidence import CompetitorEvidenceBuilder
from app.analysis.competitor.llm_analyzer import LLMStructuredCompetitorAnalyzer
from app.models.competitor_comment import CompetitorComment
from app.models.competitor_note import CompetitorNote
from app.models.competitors_analysis import CompetitorAnalysisReport
from app.models.content_opportunity import ContentOpportunity
from app.models.viral_note_breakdown import ViralNoteBreakdown
from app.repositories.competitor_report_repo import CompetitorReportRepository
from app.schemas.competitor_report import CompetitorReportCreate


class DataAvailabilityError(ValueError):
    """结构化表达业务数据不可用原因。"""

    def __init__(self, message: str, payload: dict):
        super().__init__(message)
        self.payload = payload


class CompetitorReportService:
    """编排事实证据、分析引擎、报告组装与持久化。"""

    def __init__(
        self,
        db: Session,
        analyzer: CompetitorAnalysisEngine | None = None,
        evidence_builder: CompetitorEvidenceBuilder | None = None,
        assembler: CompetitorReportAssembler | None = None,
    ):
        self.db = db
        self.repo = CompetitorReportRepository(db)
        self.analyzer = analyzer
        self._last_analysis_engine = "LLM_STRUCTURED_V1"
        self.evidence_builder = evidence_builder or CompetitorEvidenceBuilder()
        self.assembler = assembler or CompetitorReportAssembler()

    @property
    def analysis_engine(self) -> str:
        """返回当前显式选择的分析引擎标识。"""
        return self.analyzer.analysis_engine if self.analyzer else self._last_analysis_engine

    def create_report(self, data: CompetitorReportCreate) -> CompetitorAnalysisReport:
        """基于真实证据创建竞品分析报告。"""
        self._ensure_account_exists(data.account_id)
        accounts = self.repo.list_competitor_accounts(data.account_id)
        notes = self.repo.list_competitor_notes(data.account_id, data.keyword, data.limit)
        if not notes:
            state = self._empty_note_state(data.account_id, data.keyword)
            raise DataAvailabilityError(state["message"], state)
        comments = self.repo.list_comments_for_notes(data.account_id, [note.id for note in notes])
        evidence = self.evidence_builder.build(data.account_id, accounts, notes, comments)
        analyzer = self._resolve_analyzer()
        semantic = analyzer.analyze(evidence)
        self._last_analysis_engine = analyzer.analysis_engine
        report, breakdowns, opportunities = self.assembler.assemble(
            data,
            evidence,
            semantic,
            self.analysis_engine,
            self._sample_state(notes, comments),
        )
        try:
            persisted = self.repo.create_report_bundle(report, breakdowns, opportunities)
            self.db.commit()
            return persisted
        except Exception:
            self.db.rollback()
            raise

    def _resolve_analyzer(self) -> CompetitorAnalysisEngine:
        """Return the only production research analyzer: structured LLM."""
        if self.analyzer:
            return self.analyzer
        return LLMStructuredCompetitorAnalyzer()

    def get_report(self, report_id: int) -> CompetitorAnalysisReport:
        """查询竞品分析报告详情。"""
        report = self.repo.get_report(report_id)
        if report:
            return report
        raise ValueError("竞品分析报告不存在")

    def list_viral_breakdowns(self, report_id: int) -> list[ViralNoteBreakdown]:
        """查询爆款笔记拆解列表。"""
        self.get_report(report_id)
        return self.repo.list_viral_breakdowns(report_id)

    def list_opportunities(self, report_id: int) -> list[ContentOpportunity]:
        """查询内容机会列表。"""
        self.get_report(report_id)
        return self.repo.list_opportunities(report_id)

    def _ensure_account_exists(self, account_id: int) -> None:
        if not self.repo.get_account(account_id):
            raise ValueError("账号配置不存在")

    def _empty_note_state(self, account_id: int, keyword: str | None) -> dict:
        total_count = self.repo.count_competitor_notes(account_id)
        real_count = self.repo.count_competitor_notes(account_id, is_mock=False)
        keyword_total_count = self.repo.count_competitor_notes(account_id, keyword=keyword) if keyword else total_count
        keyword_real_count = self.repo.count_competitor_notes(account_id, keyword=keyword, is_mock=False) if keyword else real_count
        if total_count == 0:
            reason, message, action = "NO_COMPETITOR_NOTES", "当前账号暂无竞品笔记，请先采集或手动录入真实样本", "COLLECT_COMPETITOR_NOTES"
            hint = "请先通过真实采集链路或手动录入公开笔记，再创建竞品分析报告。"
        elif real_count == 0:
            reason, message, action = "ONLY_MOCK_COMPETITOR_NOTES", "当前只有 Mock 竞品笔记，不能用于真实竞品分析", "REPLACE_WITH_REAL_NOTES"
            hint = "请补充 MCP、ReadOnly 或手动录入的真实公开笔记样本。"
        elif keyword and keyword_total_count > 0 and keyword_real_count == 0:
            reason, message, action = "KEYWORD_MATCHED_ONLY_MOCK", "当前关键词只命中 Mock 笔记，不能用于真实竞品分析", "COLLECT_REAL_NOTES_FOR_KEYWORD"
            hint = "请围绕该关键词补充真实笔记，或移除关键词查看账号下其他真实样本。"
        elif keyword:
            reason, message, action = "KEYWORD_NO_MATCH", "当前关键词没有命中可用于分析的真实竞品笔记", "RELAX_KEYWORD_OR_COLLECT_MORE"
            hint = "请换一个更宽的关键词，或先采集/录入该关键词下的真实样本。"
        else:
            reason, message, action = "NO_USABLE_REAL_NOTES", "当前没有可用于分析的真实竞品笔记", "COLLECT_COMPETITOR_NOTES"
            hint = "请补充真实公开笔记样本后重试。"
        return {
            "data_quality": "EMPTY",
            "reason": reason,
            "action": action,
            "message": message,
            "hint": hint,
            "can_continue": False,
            "counts": {
                "total_count": total_count,
                "real_count": real_count,
                "keyword_total_count": keyword_total_count,
                "keyword_real_count": keyword_real_count,
            },
        }

    def _sample_state(self, notes: list[CompetitorNote], comments: list[CompetitorComment]) -> dict:
        if len(notes) < 3:
            return {
                "data_quality": "PARTIAL",
                "reason": "INSUFFICIENT_SAMPLE",
                "action": "CONTINUE_WITH_LOW_CONFIDENCE",
                "hint": "真实竞品笔记少于 3 条，本次报告可生成，但建议补充样本后再做运营决策。",
                "can_continue": True,
            }
        if len(comments) < 3:
            return {
                "data_quality": "PARTIAL",
                "reason": "INSUFFICIENT_COMMENT_SAMPLE",
                "action": "CONTINUE_WITH_LOW_CONFIDENCE",
                "hint": "评论样本偏少，用户需求只能作为低置信参考。",
                "can_continue": True,
            }
        return {"data_quality": "READY", "reason": "READY", "action": "CONTINUE", "hint": "", "can_continue": True}
