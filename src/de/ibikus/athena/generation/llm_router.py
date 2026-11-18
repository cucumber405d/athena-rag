"""Routes a GenerationRequest to the selected llm_target, after a Privacy Guard check.

Retrieval and generation stay strictly separate (spec section 18): this
module never touches the vector store, it only receives already-built context text.
"""

from __future__ import annotations

from de.ibikus.athena.core.config.loader import Config
from de.ibikus.athena.core.models.llm_target import GenerationRequest, GenerationResponse
from de.ibikus.athena.generation import openai_compatible
from de.ibikus.athena.generation.privacy_guard import PrivacyGuard
from de.ibikus.athena.retrieval.context_builder import estimate_tokens

_PROVIDER_CLIENTS = {
    "openai_compatible": openai_compatible.generate,
}


class LLMRouter:
    def __init__(self, config: Config, privacy_guard: PrivacyGuard):
        self._config = config
        self._privacy_guard = privacy_guard

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        target = self._config.llm_targets.get(request.llm_target)
        model = request.model or target.default_model

        decision = self._privacy_guard.check(request.domain_id, target, request.external_confirmation)
        if not decision.allowed:
            return GenerationResponse(
                answer="",
                llm_target=target.id,
                model=model,
                context_tokens_estimate=estimate_tokens(request.context_text),
                output_tokens_estimate=0,
                blocked=True,
                block_reason=decision.reason,
            )

        provider_fn = _PROVIDER_CLIENTS.get(target.provider)
        if provider_fn is None:
            raise NotImplementedError(
                f"LLM provider '{target.provider}' is not implemented yet (MVP covers openai_compatible)"
            )

        answer = provider_fn(target, request.prompt, request.context_text, model, request.temperature)
        return GenerationResponse(
            answer=answer,
            llm_target=target.id,
            model=model,
            context_tokens_estimate=estimate_tokens(request.context_text),
            output_tokens_estimate=estimate_tokens(answer),
            blocked=False,
        )
