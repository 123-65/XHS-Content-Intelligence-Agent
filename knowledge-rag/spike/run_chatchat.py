from __future__ import annotations

import json
import os
import sys
from pathlib import Path


EMBEDDING_MODEL = "qwen3.7-text-embedding"


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def configure() -> None:
    env_path = Path(os.environ.get("SPIKE_ENV_FILE", "/run/secrets/xhs.env"))
    values = load_env(env_path)
    api_key = values.get("DASHSCOPE_API_KEY") or values.get("LLM_API_KEY")
    base_url = values.get("LLM_BASE_URL")
    llm_model = values.get("LLM_MODEL")
    if not api_key or not base_url or not llm_model:
        raise SystemExit("EMBEDDING_ENV_BLOCKED: required existing configuration is absent")

    # ApiModelSettings reads environment variables before its generated YAML file.
    # Keep the existing secret in memory and use only documented PlatformConfig fields.
    os.environ["DEFAULT_EMBEDDING_MODEL"] = EMBEDDING_MODEL
    os.environ["DEFAULT_LLM_MODEL"] = llm_model
    os.environ["MODEL_PLATFORMS"] = json.dumps(
        [
            {
                "platform_name": "alibaba_model_studio",
                "platform_type": "openai",
                "api_base_url": base_url,
                "api_key": api_key,
                "api_proxy": "",
                "api_concurrencies": 5,
                "auto_detect_model": False,
                "llm_models": [llm_model],
                "embed_models": [EMBEDDING_MODEL],
                "text2image_models": [],
                "image2text_models": [],
                "rerank_models": [],
                "speech2text_models": [],
                "text2speech_models": [],
            }
        ],
        ensure_ascii=False,
    )


def main() -> None:
    configure()
    os.execvp("chatchat", ["chatchat", *sys.argv[1:]])


if __name__ == "__main__":
    main()
