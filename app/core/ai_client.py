from dataclasses import dataclass
from typing import List, Optional, Tuple

from app.core import gemini_client, groq_client
from app.core.config import settings


class AIError(Exception):
    def __init__(self, message: str, code: str = "ai_error", attempts: Optional[list] = None):
        super().__init__(message)
        self.code = code
        self.attempts = attempts or []


@dataclass
class ProviderResult:
    provider: str
    result: "gemini_client.GenerationResult"
    fallback_used: bool
    attempted: List[Tuple[str, Optional[str]]]


_NON_RETRYABLE_CODES = {"auth_failed", "not_configured", "context_overflow", "bad_request"}


def _providers_in_order() -> List[str]:
    primary = (settings.AI_PROVIDER or "groq").strip().lower()
    fallback = (settings.AI_PROVIDER_FALLBACK or "").strip().lower()
    order = [primary]
    if fallback and fallback != primary:
        order.append(fallback)
    return order


def _call_provider(name: str, prompt: str, temperature: float, max_output_tokens: int):
    if name == "groq":
        return "groq", groq_client.generate_json(
            prompt, temperature=temperature, max_output_tokens=max_output_tokens
        )
    if name == "gemini":
        return "gemini", gemini_client.generate_json(
            prompt, temperature=temperature, max_output_tokens=max_output_tokens
        )
    raise AIError(f"Unknown AI provider: {name}", code="unknown_provider")


def _parse_provider_output(name: str, text: str) -> dict:
    if name == "groq":
        return groq_client.parse_json_output(text)
    if name == "gemini":
        return gemini_client.parse_json_output(text)
    raise AIError(f"Unknown AI provider: {name}", code="unknown_provider")


def generate_json(
    prompt: str,
    *,
    temperature: float = 0.2,
    max_output_tokens: int = 8192,
) -> ProviderResult:
    providers = _providers_in_order()
    attempted: List[Tuple[str, Optional[str]]] = []

    for idx, provider in enumerate(providers):
        try:
            name, result = _call_provider(
                provider, prompt, temperature, max_output_tokens
            )
            attempted.append((name, None))
            return ProviderResult(
                provider=name,
                result=result,
                fallback_used=(idx > 0),
                attempted=attempted,
            )
        except (groq_client.GroqError, gemini_client.GeminiError) as exc:
            code = getattr(exc, "code", "")
            attempted.append((provider, f"{code}: {exc}"))

            is_last = idx == len(providers) - 1
            if is_last:
                summary = " | ".join(f"{p}: {msg}" for p, msg in attempted if msg)
                raise AIError(
                    f"All AI providers failed. {summary}",
                    code="all_providers_failed",
                    attempts=attempted,
                )
            if code == "auth_failed":
                continue
            continue
        except Exception as exc:
            attempted.append((provider, f"unexpected: {exc}"))
            if idx == len(providers) - 1:
                summary = " | ".join(f"{p}: {msg}" for p, msg in attempted if msg)
                raise AIError(
                    f"All AI providers failed. {summary}",
                    code="all_providers_failed",
                    attempts=attempted,
                )
            continue

    raise AIError("No AI providers configured", code="no_providers")


def parse_json_output(provider: str, text: str) -> dict:
    return _parse_provider_output(provider, text)
