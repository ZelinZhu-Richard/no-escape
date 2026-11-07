"""Bounded Gemini Developer API transport; no billing eligibility assumptions.

REST reference verified 2026-11-07: https://ai.google.dev/api/generate-content
This is deliberately not a Vertex AI adapter and never substitutes providers.
"""

import base64
import json
import re
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .analysis_models import RESPONSE_SCHEMA

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
MODEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")
SELECTED_MODEL = "gemini-3.5-flash-lite"
SAFE_ERRORS = {
    "authentication": "Gemini rejected the credential or project permission. Check the local API key and its Gemini API access.",
    "model_unavailable": "The selected Gemini model is unavailable to this key/project. No alternative model was called.",
    "rate_limit": "Gemini returned a rate or quota limit. Check the project's quota and billing; no retry was attempted.",
    "invalid_request": "Gemini rejected the request configuration. No retry or provider substitution was attempted.",
    "network": "Gemini could not be reached within the request timeout. No retry was attempted.",
    "incomplete": "Gemini did not return a complete structured observation. The attempt was counted; no retry was attempted.",
    "invalid_response": "Gemini returned an invalid observation or model metadata. No fixture was substituted.",
    "provider_error": "Gemini request or response validation failed. No retry or provider substitution was attempted.",
}


class ProviderError(Exception):
    """Only messages authored here are safe to expose to the application."""

    def __init__(self, message: str, *, code: str = "provider_error"):
        super().__init__(message)
        self.code = code if code in SAFE_ERRORS else "provider_error"

    @property
    def safe_message(self) -> str:
        return SAFE_ERRORS[self.code]


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass(frozen=True)
class ProviderResponse:
    document: dict
    model_version: str
    usage: dict


def generation_config(model: str) -> dict:
    """Part of cache identity: a configuration change requires a new result."""
    config = {
        "temperature": 1 if model == SELECTED_MODEL else 0,
        "candidateCount": 1,
        "maxOutputTokens": 4096 if model == SELECTED_MODEL else 1500,
        "responseMimeType": "application/json",
        "responseJsonSchema": RESPONSE_SCHEMA,
    }
    if model == SELECTED_MODEL:
        config["thinkingConfig"] = {"thinkingLevel": "MINIMAL", "includeThoughts": False}
    return config


def _http_error(error: HTTPError) -> ProviderError:
    code = {400: "invalid_request", 401: "authentication", 403: "authentication",
            404: "model_unavailable", 429: "rate_limit"}.get(error.code, "provider_error")
    return ProviderError(f"Provider request failed (HTTP {error.code}); no retry was attempted.", code=code)


def get_model_metadata(*, api_key: str, model: str) -> dict:
    """Read-only account/model preflight; sends no footage and generates no content."""
    if not MODEL_PATTERN.fullmatch(model) or not api_key or len(api_key) > 1000:
        raise ProviderError("Gemini credential/model configuration is incomplete.", code="authentication")
    request = Request(f"{API_BASE}/{model}", headers={"x-goog-api-key": api_key}, method="GET")
    try:
        with build_opener(NoRedirect()).open(request, timeout=15) as response:
            body = response.read(100_001)
        if len(body) > 100_000:
            raise ValueError("Metadata too large")
        data = json.loads(body)
        if data.get("name") != f"models/{model}" or "generateContent" not in data.get("supportedGenerationMethods", []):
            raise ValueError("Model does not support the selected method")
        if any(type(data.get(field)) is not int or data[field] <= 0 for field in ("inputTokenLimit", "outputTokenLimit")):
            raise ValueError("Missing token limits")
        return {"name": data["name"], "generate_content_supported": True,
                "input_token_limit": data.get("inputTokenLimit"),
                "output_token_limit": data.get("outputTokenLimit")}
    except HTTPError as error:
        raise _http_error(error) from None
    except (URLError, TimeoutError, OSError):
        raise ProviderError("Metadata request failed.", code="network") from None
    except (ValueError, TypeError, AttributeError):
        raise ProviderError("Metadata was not valid.", code="invalid_response") from None


def generate_content(*, api_key: str, model: str, prompt: str, frames: list[tuple[float, bytes]]) -> ProviderResponse:
    """Make one request, without automatic retries or redirects.

    AnalysisService must authorize and reserve this call first. API keys are
    headers, never query parameters; neither error bodies nor request URLs are
    emitted to the ledger or logs.
    """
    if not MODEL_PATTERN.fullmatch(model):
        raise ProviderError("The configured model identifier is invalid.")
    if not api_key or len(api_key) > 1000:
        raise ProviderError("A valid API credential is not configured.")
    if len(frames) != 3 or any(not content or len(content) > 2_000_000 for _, content in frames):
        raise ProviderError("Exactly three bounded image frames are required.")
    parts = [{"text": prompt}]
    for timestamp, content in frames:
        parts.extend([
            {"text": f"Frame at {timestamp:g} seconds in recorded clip:"},
            {"inlineData": {"mimeType": "image/jpeg", "data": base64.b64encode(content).decode("ascii")}},
        ])
    payload = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": generation_config(model),
    }
    request = Request(
        f"{API_BASE}/{model}:generateContent",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    try:
        with build_opener(NoRedirect()).open(request, timeout=30) as response:
            body = response.read(2_000_001)
        if len(body) > 2_000_000:
            raise ProviderError("Provider response exceeded the configured size limit.")
        envelope = json.loads(body)
        candidates = envelope.get("candidates", [])
        if len(candidates) != 1 or candidates[0].get("finishReason") != "STOP":
            raise ProviderError("Provider did not return a complete candidate response.", code="incomplete")
        text = "".join(p.get("text", "") for p in candidates[0].get("content", {}).get("parts", []) if not p.get("thought"))
        document = json.loads(text)
        version = envelope.get("modelVersion")
        if not isinstance(document, dict) or not isinstance(version, str) or not MODEL_PATTERN.fullmatch(version):
            raise ProviderError("Provider response metadata was incomplete.", code="invalid_response")
        raw_usage = envelope.get("usageMetadata", {})
        usage = {
            key: value for key, value in raw_usage.items()
            if key in {"promptTokenCount", "candidatesTokenCount", "totalTokenCount", "thoughtsTokenCount"}
            and type(value) is int and value >= 0
        }
        return ProviderResponse(document=document, model_version=version, usage=usage)
    except HTTPError as error:
        raise _http_error(error) from None
    except (URLError, TimeoutError, OSError):
        raise ProviderError("Provider network request failed; no retry was attempted.", code="network") from None
    except (ValueError, TypeError, KeyError, AttributeError):
        raise ProviderError("Provider response was not valid structured content.", code="invalid_response") from None
