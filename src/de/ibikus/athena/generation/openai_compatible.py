"""OpenAI-compatible chat completion client.

Works for LM Studio, Ollama, vLLM, llama.cpp server and OpenAI itself — any
endpoint speaking the /chat/completions contract.
"""

from __future__ import annotations

import os

import httpx

from de.ibikus.athena.core.models.llm_target import LLMTargetConfig

_SYSTEM_PROMPT = (
    "You are Athena, a retrieval-augmented assistant. Answer the user's question using only "
    "the provided context. If the context does not contain the answer, say so explicitly."
)


def _resolve_api_key(target: LLMTargetConfig) -> str | None:
    if target.api_key:
        return target.api_key
    if target.api_key_env:
        return os.environ.get(target.api_key_env)
    return None


def generate(
    target: LLMTargetConfig,
    prompt: str,
    context_text: str,
    model: str | None = None,
    temperature: float = 0.2,
    timeout: float = 120.0,
) -> str:
    api_key = _resolve_api_key(target)
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    user_message = f"Context:\n{context_text}\n\nQuestion:\n{prompt}"
    payload = {
        "model": model or target.default_model,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    }

    with httpx.Client(timeout=timeout) as client:
        response = client.post(f"{target.base_url.rstrip('/')}/chat/completions", json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
    return data["choices"][0]["message"]["content"]
