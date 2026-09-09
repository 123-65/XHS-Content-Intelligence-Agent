from app.llm.providers.base import OpenAICompatibleProvider


class ZhipuProvider(OpenAICompatibleProvider):
    """智谱 OpenAI-compatible Provider。"""

    name = "zhipu"
