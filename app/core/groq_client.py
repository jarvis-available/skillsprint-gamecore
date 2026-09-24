import json
import re
import time
from typing import Optional

from app.core.config import settings
from app.core.gemini_client import GenerationResult


class GroqError(Exception):
    def __init__(self, message: str, retryable: bool = False, code: str = "groq_error"):
        super().__init__(message)
        self.retryable = retryable
        self.code = code


_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_RETRY_AFTER_RE = re.compile(r"retry after\s+(\d+(?:\.\d+)?)", re.IGNORECASE)


def _is_configured() -> bool:
    return bool(settings.GROQ_API_KEY)


def _client():
    if not _is_configured():
        raise GroqError("GROQ_API_KEY not set", retryable=False, code="not_configured")
    from groq import Groq

    return Groq(api_key=settings.GROQ_API_KEY, timeout=settings.GROQ_TIMEOUT_SECONDS)


def _parse_retry_seconds(message: str) -> Optional[float]:
    match = _RETRY_AFTER_RE.search(message or "")
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def generate_json(
    prompt: str,
    *,
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_output_tokens: int = 8192,
) -> GenerationResult:
    client = _client()
    model_name = model or settings.GROQ_MODEL

    last_error: Optional[Exception] = None
    started_all = time.time()

    for attempt in range(settings.GROQ_MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=temperature,
                max_tokens=max_output_tokens,
            )
            choice = response.choices[0]
            text = (choice.message.content or "").strip()
            if not text:
                raise GroqError("Empty response", retryable=True, code="empty_response")

            token_estimate = None
            try:
                usage = getattr(response, "usage", None)
                if usage is not None:
                    token_estimate = int(getattr(usage, "total_tokens", 0)) or None
            except Exception:
                token_estimate = None

            latency_ms = int((time.time() - started_all) * 1000)
            return GenerationResult(
                text=text,
                model=model_name,
                latency_ms=latency_ms,
                retries=attempt,
                token_estimate=token_estimate,
            )

        except GroqError as exc:
            last_error = exc
            if not exc.retryable:
                raise
        except Exception as exc:
            last_error = exc
            message = str(exc).lower()

            if "invalid_api_key" in message or "unauthorized" in message or "401" in message:
                raise GroqError(
                    f"Authentication failed: {exc}", retryable=False, code="auth_failed"
                )
            if "model_not_found" in message or "does not exist" in message:
                raise GroqError(
                    f"Model not found: {exc}", retryable=False, code="model_not_found"
                )
            if "context length" in message or "context_length" in message:
                raise GroqError(
                    f"Prompt too long: {exc}", retryable=False, code="context_overflow"
                )

            retry_after = _parse_retry_seconds(str(exc))
            if not any(
                k in message
                for k in (
                    "timeout",
                    "unavailable",
                    "rate",
                    "429",
                    "503",
                    "connection",
                    "temporary",
                )
            ):
                pass

            sleep_for = retry_after if retry_after else min(2 ** attempt, 8)
            sleep_for = min(sleep_for, 60)
            if attempt < settings.GROQ_MAX_RETRIES - 1:
                time.sleep(sleep_for)
            continue

    raise GroqError(
        f"Groq generation failed after {settings.GROQ_MAX_RETRIES} attempts: {last_error}",
        retryable=False,
        code="max_retries",
    )


def parse_json_output(text: str) -> dict:
    stripped = _THINK_BLOCK_RE.sub("", text).strip()
    if stripped.startswith("```"):
        first_newline = stripped.find("\n")
        if first_newline != -1:
            stripped = stripped[first_newline + 1 :]
        if stripped.rstrip().endswith("```"):
            stripped = stripped.rstrip()[:-3]
    try:
        return json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise GroqError(f"Invalid JSON: {exc}", retryable=False, code="invalid_json")
