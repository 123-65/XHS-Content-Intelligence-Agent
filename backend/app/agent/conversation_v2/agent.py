from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.toolsets import FilteredToolset, FunctionToolset

from app.agent.conversation_v2.deps import ConversationAgentDeps
from app.agent.conversation_v2.execution_gate import ExecutionMode
from app.agent.conversation_v2.instructions import ARBITRATION_INSTRUCTIONS, BASE_INSTRUCTIONS, runtime_instructions
from app.agent.conversation_v2.outcomes import ConversationResponse
from app.agent.conversation_v2.workflow_tools import WORKFLOW_TOOLS
from app.core.config import settings


def build_conversation_agent(model=None) -> Agent[ConversationAgentDeps, ConversationResponse]:
    if model is None:
        model_name = settings.llm_control_semantic_model or "qwen3.7-flash-2026-07-15"
        provider = OpenAIProvider(base_url=settings.llm_base_url, api_key=settings.llm_api_key)
        model = OpenAIChatModel(
            model_name,
            provider=provider,
            settings={"timeout": settings.llm_timeout_seconds, "extra_body": {"enable_thinking": False}},
        )
    workflow_toolset = FilteredToolset(
        FunctionToolset(WORKFLOW_TOOLS),
        lambda ctx, tool_def: (
            ctx.deps.execution_gate.mode == ExecutionMode.BUSINESS_ACTION
            and ctx.deps.decision_context.allows(tool_def.name)
        ),
    )
    return Agent(
        model,
        output_type=ConversationResponse,
        deps_type=ConversationAgentDeps,
        instructions=(BASE_INSTRUCTIONS, ARBITRATION_INSTRUCTIONS, runtime_instructions),
        toolsets=[workflow_toolset],
        retries=1,
        name="conversation_v2",
        tool_timeout=settings.agent_workflow_tool_timeout_seconds,
    )
