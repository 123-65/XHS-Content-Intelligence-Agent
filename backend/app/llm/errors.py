class LLMError(Exception):
    """模型调用基础异常。"""


class LLMConfigError(LLMError):
    """模型配置异常。"""


class LLMResponseError(LLMError):
    """模型响应解析异常。"""
