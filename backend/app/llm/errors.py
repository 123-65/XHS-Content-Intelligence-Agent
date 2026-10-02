class LLMError(Exception):
    """Base exception for LLM calls."""


class LLMConfigError(LLMError):
    """LLM configuration exception."""


class LLMResponseError(LLMError):
    """LLM response parsing or validation exception."""


class LLMOutputParseError(LLMResponseError):
    """Model output is not valid JSON or cannot be parsed."""


class LLMSchemaValidationError(LLMResponseError):
    """Model output JSON does not match the requested schema."""


class LLMTimeoutError(LLMResponseError):
    """A finite business LLM deadline was exhausted."""

    code = "LLM_TIMEOUT"
