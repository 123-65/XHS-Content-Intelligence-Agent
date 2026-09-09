from app.llm.providers.base import OpenAICompatibleProvider


class QwenProvider(OpenAICompatibleProvider):
    """通义千问 OpenAI-compatible Provider。"""

    name = "qwen"
