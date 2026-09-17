from typing import Protocol

from app.analysis.competitor.schemas import CompetitorEvidence, CompetitorSemanticResult


class CompetitorAnalysisEngine(Protocol):
    """竞品语义分析器统一接口。"""

    analysis_engine: str

    def analyze(self, evidence: CompetitorEvidence) -> CompetitorSemanticResult:
        """仅基于给定事实证据生成结构化语义结果。"""
        ...
