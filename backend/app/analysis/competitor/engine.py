from typing import Protocol

from app.analysis.competitor.schemas import CompetitorEvidence, CompetitorSemanticResult


class CompetitorAnalysisError(ValueError):
    """竞品分析失败，携带稳定错误码供 API 和 Agent 展示。"""

    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.payload = {"error_code": code, "message": message}


class CompetitorAnalysisEngine(Protocol):
    """竞品语义分析器统一接口。"""

    analysis_engine: str

    def analyze(self, evidence: CompetitorEvidence) -> CompetitorSemanticResult:
        """仅基于给定事实证据生成结构化语义结果。"""
        ...
