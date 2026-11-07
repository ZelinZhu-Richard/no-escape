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


class ProviderError(Exception):
    """Only messages authored here are safe to expose to the application."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass(frozen=True)
class ProviderResponse:
    document: dict
    model_version: str
    usage: dict


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
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": 1500,
            "responseMimeType": "application/json",
            "responseJsonSchema": RESPONSE_SCHEMA,
        },
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
            raise ProviderError("Provider did not return a complete candidate response.")
        text = "".join(p.get("text", "") for p in candidates[0].get("content", {}).get("parts", []) if not p.get("thought"))
        document = json.loads(text)
        version = envelope.get("modelVersion")
        if not isinstance(document, dict) or not isinstance(version, str) or not MODEL_PATTERN.fullmatch(version):
            raise ProviderError("Provider response metadata was incomplete.")
        raw_usage = envelope.get("usageMetadata", {})
        usage = {
            key: value for key, value in raw_usage.items()
            if key in {"promptTokenCount", "candidatesTokenCount", "totalTokenCount", "thoughtsTokenCount"}
            and type(value) is int and value >= 0
        }
        return ProviderResponse(document=document, model_version=version, usage=usage)
    except HTTPError as error:
        raise ProviderError(f"Provider request failed (HTTP {error.code}); no retry was attempted.") from None
    except (URLError, TimeoutError, OSError):
        raise ProviderError("Provider network request failed; no retry was attempted.") from None
    except (ValueError, TypeError, KeyError, AttributeError):
        raise ProviderError("Provider response was not valid structured content.") from None
