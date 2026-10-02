from app.agent.schemas.execution import ArtifactRef, ArtifactType
from app.agent.tools.artifact_contracts import (
    AppendDraftVersionInput,
    CreateContentStrategyArtifactInput,
    CreateContentStrategyArtifactResult,
    CreateDraftV1Input,
    CreateDraftVersionInput,
    CreateDraftVersionResult,
    CreatePostPublishReviewArtifactInput,
    CreatePostPublishReviewArtifactResult,
    CreateResearchArtifactInput,
    CreateResearchArtifactResult,
    CreateStrategyCandidateInput,
    CreateStrategyCandidateResult,
)
from app.agent.tools.definitions import ToolError, ToolResult
from app.analysis.competitor.assembler import CompetitorReportAssembler
from app.repositories.competitor_report_repo import CompetitorReportRepository
from app.repositories.content_strategy_repo import ContentStrategyRepository
from app.repositories.draft_repo import DraftRepository
from app.repositories.publication_repo import PublicationRepository
from app.schemas.competitor_report import CompetitorReportCreate
from app.agent.tools.definitions import ToolName
from app.runtime.durable_operation import DurableOperationExecutor


class ArtifactToolBase:
    """五个 Artifact Tool 共用的真实失败结果映射。"""

    def _bind_transaction(self, db, repository) -> None:
        self.db = db or getattr(repository, "db", None)

    def _run(self, tool_name, data, business_write):
        if self.runtime_identity is not None:
            return DurableOperationExecutor(self.db, self.runtime_identity).execute(tool_name, data, business_write)
        result = business_write()
        if result.success:
            self._commit()
        return result

    def _commit(self) -> None:
        if self.db is not None:
            self.db.commit()

    def _rollback(self) -> None:
        if self.db is not None:
            self.db.rollback()

    def _failure(self, exc: Exception) -> ToolResult:
        """把校验或持久化异常转换为不携带伪数据的失败结果。"""
        category = "VALIDATION" if isinstance(exc, ValueError) else "PERSISTENCE"
        return ToolResult(
            success=False,
            data=None,
            error=ToolError(
                code="VALIDATION_ERROR" if category == "VALIDATION" else "PERSISTENCE_ERROR",
                category=category,
                retryable=category == "PERSISTENCE",
                safe_message="Artifact 持久化失败，输入 lineage 或数据库写入未通过校验。",
            ),
            metadata={"exception_type": type(exc).__name__},
        )


class CreateResearchArtifactTool(ArtifactToolBase):
    """通过正式 Report Bundle Owner 保存已经完成分析的 Research。"""

    name = "create_research_artifact"

    def __init__(self, db=None, repository=None, assembler=None, runtime_identity=None):
        """注入数据库、正式 Repository 与确定性 Assembler。"""
        self.repository = repository or CompetitorReportRepository(db)
        self._bind_transaction(db, self.repository)
        self.runtime_identity = runtime_identity
        self.assembler = assembler or CompetitorReportAssembler()

    def execute(self, data: CreateResearchArtifactInput) -> ToolResult[CreateResearchArtifactResult]:
        return self._run(ToolName.CREATE_RESEARCH_ARTIFACT, data, lambda: self._execute_once(data))

    def _execute_once(self, data: CreateResearchArtifactInput) -> ToolResult[CreateResearchArtifactResult]:
        """只组装并持久化语义结果，不重新调用 Analyzer 或 LLM。"""
        try:
            if data.research_evidence.account_id != data.account_ref:
                raise ValueError("Research evidence 与 account_ref 不一致")
            if self.repository.get_account(data.account_ref) is None:
                raise ValueError("账号配置不存在")
            create = CompetitorReportCreate(
                account_id=data.account_ref,
                name=data.report_name,
                keyword=data.keyword,
                target_metric=data.target_metric,
                analysis_engine=data.analysis_engine,
            )
            report, breakdowns, opportunities = self.assembler.assemble(
                create,
                data.research_evidence,
                data.research_result,
                data.analysis_engine,
                data.sample_state,
            )
            persisted = self.repository.create_report_bundle(report, breakdowns, opportunities)
            output = ToolResult(
                success=True,
                data=CreateResearchArtifactResult(
                    artifact_ref=ArtifactRef(type=ArtifactType.RESEARCH, id=persisted.id),
                    created_at=persisted.created_at,
                    evidence_refs=data.evidence_refs,
                    lineage_refs=data.source_refs,
                ),
            )
            return output
        except Exception as exc:
            self._rollback()
            return self._failure(exc)


class CreateContentStrategyArtifactTool(ArtifactToolBase):
    """通过 ContentStrategyRepository 保存策略及其真实派生机会。"""

    name = "create_content_strategy_artifact"

    def __init__(self, db=None, repository=None, runtime_identity=None):
        """注入唯一 Content Strategy Persistence Owner。"""
        self.repository = repository or ContentStrategyRepository(db)
        self._bind_transaction(db, self.repository)
        self.runtime_identity = runtime_identity

    def execute(self, data: CreateContentStrategyArtifactInput) -> ToolResult[CreateContentStrategyArtifactResult]:
        return self._run(ToolName.CREATE_CONTENT_STRATEGY_ARTIFACT, data, lambda: self._execute_once(data))

    def _execute_once(self, data: CreateContentStrategyArtifactInput) -> ToolResult[CreateContentStrategyArtifactResult]:
        """校验输入身份后委托 Repository 完成完整 bundle 映射。"""
        try:
            result = data.strategy_result
            if result.account_id != data.account_ref:
                raise ValueError("Strategy account lineage mismatch")
            if result.research_report_id != data.research_artifact_ref:
                raise ValueError("Strategy research lineage mismatch")
            artifact, opportunities = self.repository.create_strategy_bundle(result)
            output = ToolResult(
                success=True,
                data=CreateContentStrategyArtifactResult(
                    artifact_ref=ArtifactRef(type=ArtifactType.CONTENT_STRATEGY, id=artifact.id),
                    research_artifact_ref=artifact.research_artifact_id,
                    generated_opportunity_refs=[item.id for item in opportunities],
                    created_at=artifact.created_at,
                ),
            )
            return output
        except Exception as exc:
            self._rollback()
            return self._failure(exc)


class CreateDraftVersionTool(ArtifactToolBase):
    """以同一 Tool 创建 Draft V1 或在同一 Root 下追加 Revision。"""

    name = "create_draft_version"

    def __init__(self, db=None, repository=None, runtime_identity=None):
        """注入唯一 Draft Persistence Owner。"""
        self.repository = repository or DraftRepository(db)
        self._bind_transaction(db, self.repository)
        self.runtime_identity = runtime_identity

    def execute(self, data: CreateDraftVersionInput) -> ToolResult[CreateDraftVersionResult]:
        return self._run(ToolName.CREATE_DRAFT_VERSION, data, lambda: self._execute_once(data))

    def _execute_once(self, data: CreateDraftVersionInput) -> ToolResult[CreateDraftVersionResult]:
        """保持 Root Ref 稳定，并将 parent_draft_ref 解释为父 Version ID。"""
        try:
            request = data.root
            if isinstance(request, CreateDraftV1Input):
                root, version = self.repository.create_agent_draft_root(
                    account_id=request.account_ref,
                    strategy_artifact_id=request.strategy_artifact_ref,
                    opportunity_id=request.opportunity_ref,
                    content_goal=request.content_goal,
                    content=request.content,
                    metadata=request.metadata,
                    context=request.context,
                )
            elif isinstance(request, AppendDraftVersionInput):
                root, version = self.repository.append_agent_draft_version(
                    draft_id=request.draft_ref,
                    parent_version_id=request.parent_draft_ref,
                    created_from=request.created_from,
                    content=request.content,
                    metadata=request.metadata,
                    context=request.context,
                    applied_changes=request.applied_changes,
                )
            else:
                raise ValueError("未知 Draft Version action")
            output = ToolResult(
                success=True,
                data=CreateDraftVersionResult(
                    draft_ref=root.id,
                    draft_version_ref=version.id,
                    version=version.version,
                    parent_draft_ref=version.parent_version_id,
                    created_from=version.created_from,
                    created_at=version.created_at,
                ),
            )
            return output
        except Exception as exc:
            self._rollback()
            return self._failure(exc)


class CreatePostPublishReviewArtifactTool(ArtifactToolBase):
    """保存已经完成分析的发布后复盘，不触发语义分析或 Memory。"""

    name = "create_post_publish_review_artifact"

    def __init__(self, db=None, repository=None, runtime_identity=None):
        """注入统一 Publication Persistence Owner。"""
        self.repository = repository or PublicationRepository(db)
        self._bind_transaction(db, self.repository)
        self.runtime_identity = runtime_identity

    def execute(self, data: CreatePostPublishReviewArtifactInput) -> ToolResult[CreatePostPublishReviewArtifactResult]:
        return self._run(ToolName.CREATE_POST_PUBLISH_REVIEW_ARTIFACT, data, lambda: self._execute_once(data))

    def _execute_once(self, data: CreatePostPublishReviewArtifactInput) -> ToolResult[CreatePostPublishReviewArtifactResult]:
        """验证 PublishedNote、Draft 与账号 lineage 后保存 ReviewReport。"""
        try:
            note = self.repository.get_note(data.published_note_ref)
            if note is None or note.account_id != data.account_ref:
                raise ValueError("Published Note 不存在或不属于当前账号")
            if note.draft_id != data.draft_ref:
                raise ValueError("Published Note 与 draft_ref 不一致")
            report = self.repository.create_post_review(
                note,
                data.account_ref,
                data.review_result,
                metadata=data.metadata,
            )
            if report.published_note_id != data.published_note_ref:
                raise ValueError("PostPublishReview PublishedNote lineage mismatch")
            output = ToolResult(
                success=True,
                data=CreatePostPublishReviewArtifactResult(
                    artifact_ref=ArtifactRef(type=ArtifactType.POST_PUBLISH_REVIEW, id=report.id),
                    published_note_ref=report.published_note_id,
                    created_at=report.created_at,
                ),
            )
            return output
        except Exception as exc:
            self._rollback()
            return self._failure(exc)


class CreateStrategyCandidateTool(ArtifactToolBase):
    """创建持久化 PROPOSED Candidate，并以数据库主键作为稳定身份。"""

    name = "create_strategy_candidate"

    def __init__(self, db=None, repository=None, runtime_identity=None):
        """注入统一 Publication Persistence Owner。"""
        self.repository = repository or PublicationRepository(db)
        self._bind_transaction(db, self.repository)
        self.runtime_identity = runtime_identity

    def execute(self, data: CreateStrategyCandidateInput) -> ToolResult[CreateStrategyCandidateResult]:
        return self._run(ToolName.CREATE_STRATEGY_CANDIDATE, data, lambda: self._execute_once(data))

    def _execute_once(self, data: CreateStrategyCandidateInput) -> ToolResult[CreateStrategyCandidateResult]:
        """保存与 Review 快照匹配的 Candidate，不调用 Strategy Memory。"""
        try:
            candidate = self.repository.create_strategy_candidate(
                account_id=data.account_ref,
                review_report_id=data.post_publish_review_ref,
                candidate=data.candidate,
            )
            output = ToolResult(
                success=True,
                data=CreateStrategyCandidateResult(
                    strategy_candidate_ref=f"STRATEGY_CANDIDATE:{candidate.id}",
                    status="PROPOSED",
                    review_report_ref=candidate.review_report_id,
                    created_at=candidate.created_at,
                ),
            )
            return output
        except Exception as exc:
            self._rollback()
            return self._failure(exc)
