import json
import re
import time
from dataclasses import dataclass
from typing import Optional

from app.core.config import settings


_RETRY_DELAY_RE = re.compile(r"retry_delay\s*{\s*seconds:\s*(\d+)", re.IGNORECASE)


def _parse_retry_delay(message: str) -> Optional[int]:
    match = _RETRY_DELAY_RE.search(message or "")
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


class GeminiError(Exception):
    def __init__(self, message: str, retryable: bool = False, code: str = "gemini_error"):
        super().__init__(message)
        self.retryable = retryable
        self.code = code


@dataclass
class GenerationResult:
    text: str
    model: str
    latency_ms: int
    retries: int
    token_estimate: Optional[int] = None


def _is_configured() -> bool:
    return bool(settings.GEMINI_API_KEY)


def _client():
    if not _is_configured():
        raise GeminiError("GEMINI_API_KEY not set", retryable=False, code="not_configured")
    import google.generativeai as genai

    genai.configure(api_key=settings.GEMINI_API_KEY)
    return genai


def generate_json(
    prompt: str,
    *,
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_output_tokens: int = 8192,
) -> GenerationResult:
    genai = _client()
    model_name = model or settings.GEMINI_MODEL

    generation_config = {
        "temperature": temperature,
        "max_output_tokens": max_output_tokens,
        "response_mime_type": "application/json",
    }

    last_error: Optional[Exception] = None
    started_all = time.time()

    for attempt in range(settings.GEMINI_MAX_RETRIES):
        started = time.time()
        try:
            model_obj = genai.GenerativeModel(
                model_name=model_name,
                generation_config=generation_config,
            )
            response = model_obj.generate_content(
                prompt,
                request_options={"timeout": settings.GEMINI_TIMEOUT_SECONDS},
            )
            text = getattr(response, "text", None) or ""
            if not text.strip():
                raise GeminiError("Empty response", retryable=True, code="empty_response")

            latency_ms = int((time.time() - started_all) * 1000)
            token_estimate = None
            try:
                usage = getattr(response, "usage_metadata", None)
                if usage is not None:
                    token_estimate = int(getattr(usage, "total_token_count", 0)) or None
            except Exception:
                token_estimate = None

            return GenerationResult(
                text=text,
                model=model_name,
                latency_ms=latency_ms,
                retries=attempt,
                token_estimate=token_estimate,
            )

        except GeminiError as exc:
            last_error = exc
            if not exc.retryable:
                raise
        except Exception as exc:
            last_error = exc
            raw_message = str(exc)
            message = raw_message.lower()
            if "api key" in message or "unauthorized" in message or "401" in message:
                raise GeminiError(
                    f"Authentication failed: {exc}", retryable=False, code="auth_failed"
                )
            if "invalid" in message and "api" in message and "429" not in message:
                raise GeminiError(
                    f"Invalid API request: {exc}", retryable=False, code="bad_request"
                )
            if not any(k in message for k in ("timeout", "unavailable", "resource", "rate", "429", "503", "quota")):
                pass

            retry_delay = _parse_retry_delay(raw_message)
            sleep_for = retry_delay if retry_delay else min(2 ** attempt, 8)
            sleep_for = min(sleep_for, 60)
            if attempt < settings.GEMINI_MAX_RETRIES - 1:
                time.sleep(sleep_for)
            continue

        elapsed = time.time() - started
        sleep_for = min(2 ** attempt, 8)
        if elapsed < 1:
            time.sleep(sleep_for)

    raise GeminiError(
        f"Gemini generation failed after {settings.GEMINI_MAX_RETRIES} attempts: {last_error}",
        retryable=False,
        code="max_retries",
    )


def parse_json_output(text: str) -> dict:
    stripped = text.strip()
    if stripped.startswith("```"):
        first_newline = stripped.find("\n")
        if first_newline != -1:
            stripped = stripped[first_newline + 1 :]
        if stripped.rstrip().endswith("```"):
            stripped = stripped.rstrip()[:-3]
    try:
        return json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise GeminiError(f"Invalid JSON: {exc}", retryable=False, code="invalid_json")
