from app.llm.providers.base import OpenAICompatibleProvider


class DeepSeekProvider(OpenAICompatibleProvider):
    """DeepSeek OpenAI-compatible Provider。"""

    name = "deepseek"
