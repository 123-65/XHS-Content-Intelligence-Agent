"""Command-line smoke test for the configured LLM provider."""

import argparse
import sys
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.llm.client import LLMClient
from app.llm.errors import LLMError
from app.llm.router import llm_health
from app.schemas.provider_status import ProviderErrorCode


def main() -> int:
    """执行 LLM 连通性测试。"""
    parser = argparse.ArgumentParser(description="LLM Provider smoke test")
    parser.add_argument("--provider", default=None, help="显式指定 provider，例如 deepseek/qwen/zhipu/mock")
    parser.add_argument("--prompt", default="请用一句话回答：LLM 连通性测试成功。")
    args = parser.parse_args()

    health = llm_health()
    print("LLM health:", health)

    started_at = perf_counter()
    try:
        client = LLMClient(provider_name=args.provider)
        result = client.generate_text(args.prompt, prompt_key="llm_smoke_test", prompt_version="v1")
        print("provider:", result.provider)
        print("model:", result.model)
        print("available:", True)
        print("is_mock:", result.is_mock)
        print("latency_ms:", result.latency_ms)
        print("text_preview:", result.text[:120])
        return 0
    except LLMError as exc:
        error_message = str(exc)
        error_code = error_message.split(":", 1)[0]
        latency_ms = max(0, int((perf_counter() - started_at) * 1000))
        print("provider:", args.provider or health.get("requested_provider"))
        print("model:", health.get("model"))
        print("available:", False)
        print("is_mock:", False)
        print("latency_ms:", latency_ms)
        print("error_code:", error_code)
        print("error:", error_message)
        return 1
    except Exception as exc:
        latency_ms = max(0, int((perf_counter() - started_at) * 1000))
        print("provider:", args.provider or health.get("requested_provider"))
        print("model:", health.get("model"))
        print("available:", False)
        print("is_mock:", False)
        print("latency_ms:", latency_ms)
        print("error_code:", ProviderErrorCode.LLM_PROVIDER_UNAVAILABLE.value)
        print("error:", f"{ProviderErrorCode.LLM_PROVIDER_UNAVAILABLE.value}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
