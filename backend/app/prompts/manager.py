import importlib
import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models.prompt_template import PromptTemplate


@dataclass
class RenderedPrompt:
    """Rendered prompt payload with template metadata."""

    template: PromptTemplate
    system_prompt: str
    user_prompt: str
    prompt_name: str
    prompt_version: str
    input_payload: dict[str, Any]


class PromptManager:
    """Load prompt files, render variables, and persist prompt versions."""

    def __init__(self, db: Session):
        """Initialize the prompt manager."""
        self.db = db

    def render(self, module_path: str, variables: dict[str, Any], output_schema: dict) -> RenderedPrompt:
        """Render a prompt module with the supplied variables."""
        module = importlib.import_module(module_path)
        template = self._ensure_template(module, output_schema)
        context_json = json.dumps(variables.get("context", {}), ensure_ascii=False, indent=2, default=str)
        user_prompt = template.user_template.format(
            context_json=context_json,
            regenerate_scope=variables.get("regenerate_scope", "all"),
            protocol_block=module.protocol_block(),
        )
        return RenderedPrompt(
            template=template,
            system_prompt=template.system_prompt,
            user_prompt=user_prompt,
            prompt_name=template.prompt_name,
            prompt_version=template.prompt_version,
            input_payload=variables,
        )

    def _ensure_template(self, module, output_schema: dict) -> PromptTemplate:
        """Create the prompt template version record when it is missing."""
        template = (
            self.db.query(PromptTemplate)
            .filter(
                PromptTemplate.prompt_name == module.PROMPT_NAME,
                PromptTemplate.prompt_version == module.PROMPT_VERSION,
            )
            .one_or_none()
        )
        if template:
            return template

        template = PromptTemplate(
            prompt_name=module.PROMPT_NAME,
            prompt_version=module.PROMPT_VERSION,
            template_path=module.TEMPLATE_PATH,
            system_prompt=module.SYSTEM_PROMPT,
            user_template=module.USER_TEMPLATE,
            output_schema=output_schema,
            status="ACTIVE",
        )
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        return template
