from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


MODEL = "qwen3.7-text-embedding"
DIMENSIONS = 1024
INPUT = "Agent Tool Calling 的核心是让模型根据上下文选择工具。"


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def endpoint_facts(base_url: str) -> tuple[str, str, bool]:
    parsed = urlparse(base_url)
    host = parsed.hostname or ""
    if "cn-beijing" in host or host == "dashscope.aliyuncs.com":
        region = "BEIJING"
    elif "ap-southeast-1" in host or host == "dashscope-intl.aliyuncs.com":
        region = "SINGAPORE"
    else:
        region = "UNRESOLVED"
    endpoint_type = (
        "OPENAI_COMPATIBLE"
        if parsed.path.rstrip("/").endswith("/compatible-mode/v1")
        else "UNRESOLVED"
    )
    workspace_embedded = host.startswith("llm-") and ".maas.aliyuncs.com" in host
    return region, endpoint_type, workspace_embedded


def main() -> int:
    env_path = Path(os.environ.get("SPIKE_ENV_FILE", "/run/secrets/xhs.env"))
    values = load_env(env_path)
    api_key = values.get("DASHSCOPE_API_KEY") or values.get("LLM_API_KEY")
    base_url = values.get("LLM_BASE_URL", "").rstrip("/")
    region, endpoint_type, workspace_embedded = endpoint_facts(base_url)

    if not api_key or not base_url:
        print(
            json.dumps(
                {
                    "status": "EMBEDDING_ENV_BLOCKED",
                    "api_key_present": bool(api_key),
                    "base_url_present": bool(base_url),
                }
            )
        )
        return 2
    if endpoint_type != "OPENAI_COMPATIBLE" or region == "UNRESOLVED":
        print(
            json.dumps(
                {
                    "status": "EMBEDDING_ENV_BLOCKED",
                    "reason": "unrecognized regional compatible base URL",
                    "region": region,
                    "endpoint_type": endpoint_type,
                }
            )
        )
        return 2

    request = urllib.request.Request(
        f"{base_url}/embeddings",
        data=json.dumps(
            {
                "model": MODEL,
                "input": INPUT,
                "dimensions": DIMENSIONS,
                "encoding_format": "float",
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = json.loads(response.read().decode("utf-8"))
            http_status = response.status
    except urllib.error.HTTPError as exc:
        error_code = "HTTP_ERROR"
        try:
            error_body = json.loads(exc.read().decode("utf-8"))
            error_code = str(error_body.get("error", {}).get("code") or error_code)
        except Exception:
            pass
        print(
            json.dumps(
                {
                    "status": "EMBEDDING_API_FAILED",
                    "http_status": exc.code,
                    "error_code": error_code,
                    "region": region,
                    "endpoint_type": endpoint_type,
                    "workspace_id_present": workspace_embedded,
                    "model_requested": MODEL,
                    "fallback": 0,
                }
            )
        )
        return 3
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "EMBEDDING_API_FAILED",
                    "error_type": type(exc).__name__,
                    "region": region,
                    "endpoint_type": endpoint_type,
                    "workspace_id_present": workspace_embedded,
                    "model_requested": MODEL,
                    "fallback": 0,
                }
            )
        )
        return 3

    data = body.get("data") or []
    vector = data[0].get("embedding") if data else None
    response_model = body.get("model") or MODEL
    result = {
        "status": "PASS" if http_status == 200 else "EMBEDDING_API_FAILED",
        "http_status": http_status,
        "region": region,
        "endpoint_type": endpoint_type,
        "workspace_id_present": workspace_embedded,
        "model_requested": MODEL,
        "model_response": response_model,
        "vector_length": len(vector) if isinstance(vector, list) else 0,
        "vector_nonempty": bool(vector),
        "fallback": 0,
        "chat_completion_calls": 0,
    }
    if (
        result["status"] != "PASS"
        or response_model != MODEL
        or result["vector_length"] != DIMENSIONS
        or not result["vector_nonempty"]
    ):
        result["status"] = "EMBEDDING_API_FAILED"
        print(json.dumps(result, ensure_ascii=False))
        return 4

    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
