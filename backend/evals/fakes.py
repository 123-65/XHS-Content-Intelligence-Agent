import json
from typing import TypeVar

from pydantic import BaseModel

from app.schemas.llm import LLMStructuredResult, LLMUsage

T = TypeVar("T", bound=BaseModel)


class FakeEvalLLMClient:
    """仅供离线评测使用的确定性结构化客户端。"""

    def generate_structured(self, prompt: str, schema_model: type[T]) -> LLMStructuredResult:
        """返回满足评测 Schema 的固定数据。"""
        payload = {
            "title_candidates": [
                "AI Agent project: start from the business loop",
                "Build the workflow before choosing a framework",
                "A practical Agent project path for beginners",
            ],
            "recommended_title": "AI Agent project: start from the business loop",
            "cover_text": "AI Agent project path",
            "cover_subtitle": "Business loop first, framework later",
            "body_text": (
                "Connect collection, analysis, experiments, drafting, and review into one "
                "traceable workflow before optimizing individual framework choices."
            ),
            "image_script": [
                {"index": 1, "title": "Start point", "content": "Define the account goal.", "visual_hint": "Large cover text"},
                {"index": 2, "title": "Data loop", "content": "Connect real evidence.", "visual_hint": "Simple flow"},
                {"index": 3, "title": "Experiment", "content": "Test one variable.", "visual_hint": "Checklist"},
                {"index": 4, "title": "Review", "content": "Keep the evidence trail.", "visual_hint": "Field table"},
            ],
            "tag_list": ["AI Agent", "backend project", "content growth", "FastAPI"],
            "keyword_list": ["AI Agent project", "content experiment", "prompt log"],
            "cta_text": "Use this workflow as a project checklist.",
        }
        data = schema_model.model_validate(payload)
        return LLMStructuredResult(
            data=data,
            text=json.dumps(data.model_dump(), ensure_ascii=False),
            model="fake-eval",
            provider="fake-eval",
            usage=LLMUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
            estimated_cost=0,
            raw_response_id="fake-eval-structured",
            is_mock=True,
        )
