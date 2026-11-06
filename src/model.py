"""Minimal chat adapter for local /v1 servers (llama.cpp or Ollama)."""
import json
import os
import urllib.request
import urllib.error

DEFAULT_MODEL = "Qwen3-0.6B-Q8_0"


def chat(messages, schema=None, max_tokens=900):
    base = os.getenv("MODEL_BASE_URL", "http://127.0.0.1:8081/v1").rstrip("/")
    model = os.getenv("MODEL_NAME", DEFAULT_MODEL)
    payload = {"model": model, "messages": messages, "temperature": 0,
               "seed": 42, "max_tokens": max_tokens,
               "chat_template_kwargs": {"enable_thinking": False}}
    if schema:
        payload["response_format"] = {"type": "json_schema", "json_schema": {
            "name": "answer", "strict": True, "schema": schema}}
    headers = {"Content-Type": "application/json"}
    key = os.getenv("MODEL_API_KEY")
    if key:
        headers["Authorization"] = "Bearer " + key
    request = urllib.request.Request(base + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers=headers)
    # Local requests must not be redirected to the host's HTTP proxy.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({})) if base.startswith(
        ("http://127.0.0.1", "http://localhost")) else urllib.request.build_opener()
    try:
        with opener.open(request, timeout=180) as response:
            raw = json.load(response)
    except (OSError, urllib.error.URLError) as exc:
        raise RuntimeError("模型服务不可用。请按 README 启动模型，或用 --mode offline 演示工具。" + str(exc)) from exc
    content = raw["choices"][0]["message"].get("content", "")
    return {"content": content, "usage": raw.get("usage", {}), "model": model}
