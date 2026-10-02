from collections.abc import AsyncIterator
import base64
import hashlib
import logging

try:
    from openai import APIStatusError, AsyncOpenAI, OpenAI
except Exception:  # pragma: no cover - offline tests may not install openai.
    APIStatusError = Exception
    AsyncOpenAI = None
    OpenAI = None

from insight_rag.core.config import settings

logger = logging.getLogger(__name__)


def _client() -> AsyncOpenAI:
    if AsyncOpenAI is None:
        raise RuntimeError("openai package is not installed")
    if not settings.active_api_key or settings.active_api_key == "replace-me":
        env_name = "QWEN_API_KEY" if settings.active_provider == "qwen" else "OPENAI_API_KEY"
        raise RuntimeError(f"{env_name} is not configured")
    return AsyncOpenAI(api_key=settings.active_api_key, base_url=settings.active_base_url)


def _sync_client() -> OpenAI:
    if OpenAI is None:
        raise RuntimeError("openai package is not installed")
    if not settings.active_api_key or settings.active_api_key == "replace-me":
        env_name = "QWEN_API_KEY" if settings.active_provider == "qwen" else "OPENAI_API_KEY"
        raise RuntimeError(f"{env_name} is not configured")
    return OpenAI(api_key=settings.active_api_key, base_url=settings.active_base_url)


async def embed_texts(texts: list[str]) -> list[list[float]]:
    texts = [text for text in texts if text.strip()]
    if not texts:
        return []
    if settings.llm_provider.strip().lower() == "mock" or AsyncOpenAI is None:
        return [_mock_embedding(text, settings.active_embedding_dim) for text in texts]
    client = _client()
    vectors: list[list[float]] = []
    batch_size = 10
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        try:
            response = await client.embeddings.create(
                model=settings.active_embedding_model,
                input=batch,
                dimensions=settings.active_embedding_dim,
            )
        except APIStatusError as exc:
            if "dimension" not in str(exc).lower():
                raise
            response = await client.embeddings.create(model=settings.active_embedding_model, input=batch)
        vectors.extend(item.embedding for item in response.data)
    if vectors and len(vectors[0]) != settings.active_embedding_dim:
        raise RuntimeError(
            f"Embedding dimension mismatch: model returned {len(vectors[0])}, "
            f"but {settings.active_provider} is configured as {settings.active_embedding_dim}. "
            "Update QWEN_EMBEDDING_DIM or EMBEDDING_DIM to match the selected embedding model."
        )
    return vectors


async def chat_completion(messages: list[dict[str, str]]) -> str:
    if settings.llm_provider.strip().lower() == "mock" or AsyncOpenAI is None:
        return messages[-1]["content"] if messages else ""
    client = _client()
    response = await client.chat.completions.create(model=settings.active_chat_model, messages=messages)
    return response.choices[0].message.content or ""


def ocr_image_bytes(data: bytes, content_type: str = "image/png") -> str:
    if settings.llm_provider.strip().lower() == "mock" or OpenAI is None or not settings.active_api_key_configured:
        return _mock_ocr_text(data)
    try:
        return _vision_completion(
            data,
            content_type,
            settings.qwen_ocr_model,
            "Extract all readable text from this image. Return plain text only.",
        )
    except Exception as exc:
        logger.warning("ocr.failed model=%s bytes=%s error=%s", settings.qwen_ocr_model, len(data), exc)
        return _mock_ocr_text(data)


def caption_image_bytes(data: bytes, content_type: str = "image/png") -> str:
    if settings.llm_provider.strip().lower() == "mock" or OpenAI is None or not settings.active_api_key_configured:
        return _mock_caption_text(data)
    try:
        return _vision_completion(
            data,
            content_type,
            settings.qwen_vl_model,
            (
                "Describe this academic image for enterprise multimodal RAG. "
                "If it is a figure, chart, diagram, or table image, include the visible figure/table number, "
                "axes, labels, metrics, legends, and key numeric values. Answer in the document language when clear."
            ),
        )
    except Exception as exc:
        logger.warning("caption.failed model=%s bytes=%s error=%s", settings.qwen_vl_model, len(data), exc)
        return _mock_caption_text(data)


async def stream_chat_completion(messages: list[dict[str, str]]) -> AsyncIterator[str]:
    if settings.llm_provider.strip().lower() == "mock" or AsyncOpenAI is None:
        yield messages[-1]["content"] if messages else ""
        return
    client = _client()
    stream = await client.chat.completions.create(model=settings.active_chat_model, messages=messages, stream=True)
    async for event in stream:
        delta = event.choices[0].delta.content
        if delta:
            yield delta


def _mock_embedding(text: str, dim: int) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return [((digest[index % len(digest)] / 255.0) * 2) - 1 for index in range(dim)]


def _vision_completion(data: bytes, content_type: str, model: str, prompt: str) -> str:
    encoded = base64.b64encode(data).decode("ascii")
    response = _sync_client().chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{content_type};base64,{encoded}"}},
                ],
            }
        ],
    )
    return (response.choices[0].message.content or "").strip()


def _mock_ocr_text(data: bytes) -> str:
    digest = hashlib.sha256(data).hexdigest()[:12]
    return f"Mock OCR text for image {digest}: Accuracy Recall GraphRAG RAG"


def _mock_caption_text(data: bytes) -> str:
    digest = hashlib.sha256(data).hexdigest()[:12]
    return f"Mock image caption for asset {digest}. Figure shows a comparison chart with GraphRAG and RAG metrics."

