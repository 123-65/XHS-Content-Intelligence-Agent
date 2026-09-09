import json
from typing import TypeVar

from pydantic import BaseModel

from app.core.config import settings
from app.context.context_slots import BuiltContext
from app.schemas.llm import LLMResult, LLMStructuredResult, LLMUsage

T = TypeVar("T", bound=BaseModel)


class MockLLMClient:
    """Mock LLM client used when LLM_API_KEY is not configured."""

    def __init__(self):
        """Initialize the mock client."""
        self.model = f"mock-{settings.llm_model}"
        self.provider = f"mock-{settings.llm_provider}"

    def generate_text(self, prompt: str, system_prompt: str | None = None, model: str | None = None) -> LLMResult:
        """Generate deterministic mock text."""
        usage = LLMUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0)
        return LLMResult(
            text="MockLLMClient generated a deterministic draft-safe text.",
            model=model or self.model,
            provider=self.provider,
            usage=usage,
            estimated_cost=0,
            raw_response_id="mock-text-response",
            is_mock=True,
        )

    def generate_structured(
        self,
        prompt: str,
        schema_model: type[T],
        system_prompt: str | None = None,
        model: str | None = None,
    ) -> LLMStructuredResult:
        """Generate deterministic structured data matching the target schema."""
        data = self._mock_data(schema_model)
        parsed = schema_model.model_validate(data)
        text = json.dumps(parsed.model_dump(), ensure_ascii=False)
        usage = LLMUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0)
        return LLMStructuredResult(
            data=parsed,
            text=text,
            model=model or self.model,
            provider=self.provider,
            usage=usage,
            estimated_cost=0,
            raw_response_id="mock-structured-response",
            is_mock=True,
        )

    def generate_text_with_context(self, context: BuiltContext, model: str | None = None) -> LLMResult:
        """Generate deterministic mock text from governed context."""
        return self.generate_text(context.user_prompt, context.system_prompt, model)

    def generate_structured_with_context(self, context: BuiltContext, schema_model: type[T], model: str | None = None) -> LLMStructuredResult:
        """Generate deterministic mock structured data from governed context."""
        return self.generate_structured(context.user_prompt, schema_model, context.system_prompt, model)

    def _mock_data(self, schema_model: type[T]) -> dict:
        """Choose a deterministic mock payload for the requested schema."""
        factories = {
            "DraftGenerateV2Result": self._draft_generate_result,
            "LLMTestAnalysisResult": self._llm_test_result,
        }
        return factories.get(schema_model.__name__, self._generic_result)()

    def _draft_generate_result(self) -> dict:
        """Generate a deterministic draft payload."""
        return {
            "title_candidates": [
                "AI Agent project: start from the business loop",
                "Before learning frameworks, finish the content workflow",
                "A practical Agent project path for beginners",
            ],
            "recommended_title": "AI Agent project: start from the business loop",
            "cover_text": "AI Agent project path",
            "cover_subtitle": "Business loop first, framework later",
            "body_text": (
                "Many beginners start an AI Agent project by chasing frameworks, then get stuck. "
                "A better path is to connect the real workflow first: collect seed data, analyze "
                "competitor notes, generate opportunities, design experiments, create drafts, and "
                "review results. This gives the project a clear goal, visible data flow, and a "
                "story that can be explained in an interview without overstating outcomes."
            ),
            "image_script": [
                {"index": 1, "title": "Start point", "content": "Define the account and experiment goal.", "visual_hint": "Large cover text"},
                {"index": 2, "title": "Data loop", "content": "Connect seed collection and competitor analysis.", "visual_hint": "Simple flow"},
                {"index": 3, "title": "Experiment card", "content": "Turn opportunity evidence into testable variables.", "visual_hint": "Checklist"},
                {"index": 4, "title": "Draft output", "content": "Generate draft fields and keep prompt logs.", "visual_hint": "Field table"},
            ],
            "tag_list": ["AI Agent", "backend project", "content growth", "FastAPI"],
            "keyword_list": ["AI Agent project", "content experiment", "prompt log"],
            "cta_text": "Save this workflow as a project checklist and compare it with your current progress.",
        }

    def _llm_test_result(self) -> dict:
        """Generate a deterministic LLM test analysis payload."""
        return {"summary": "Mock structured analysis result.", "suggestions": ["Keep structure clear", "Add evidence"], "score": 88}

    def _generic_result(self) -> dict:
        """Generate a fallback mock payload."""
        return {}
