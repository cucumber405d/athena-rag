"""LLM target / generation request-response models."""

from __future__ import annotations

from pydantic import BaseModel


class LLMTargetConfig(BaseModel):
    id: str
    title: str
    provider: str  # openai_compatible | anthropic
    base_url: str | None = None
    api_key_env: str | None = None
    api_key: str | None = None
    default_model: str
    privacy_level: str = "local"  # local | local_or_lan | external


class GenerationRequest(BaseModel):
    prompt: str
    context_text: str
    llm_target: str
    model: str | None = None
    temperature: float = 0.2
    external_confirmation: bool = False
    domain_id: str | None = None


class GenerationResponse(BaseModel):
    answer: str
    llm_target: str
    model: str
    context_tokens_estimate: int
    output_tokens_estimate: int
    blocked: bool = False
    block_reason: str | None = None
