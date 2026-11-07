"""Exercise the real REST adapter against an in-memory transport, never the network."""

import io
import json
from urllib.error import HTTPError

import pytest

from api import gemini
from api.gemini import NoRedirect, ProviderError, generate_content


def envelope(**updates):
    payload = {
        "candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps({
            "candidate": False, "category": "none", "title": "No candidate",
            "observations": [], "unknowns": ["Test only"],
        })}]}}],
        "modelVersion": "test-version",
        "usageMetadata": {"totalTokenCount": 20, "irrelevantSecret": "never-store"},
    }
    return {**payload, **updates}


def setup_fake(monkeypatch, payload):
    captured = []
    class Opener:
        def open(self, request, timeout):
            captured.append((request, timeout))
            return io.BytesIO(json.dumps(payload).encode())
    monkeypatch.setattr(gemini, "build_opener", lambda *handlers: Opener())
    return captured


def call():
    return generate_content(api_key="unit-test-key", model="test-model", prompt="Inspect frames", frames=[(t, b"fake-jpeg") for t in (1.0, 4.0, 8.0)])


def test_request_uses_header_secret_bounded_images_and_schema(monkeypatch):
    captured = setup_fake(monkeypatch, envelope())
    result = call()
    request, timeout = captured[0]
    assert request.full_url == "https://generativelanguage.googleapis.com/v1beta/models/test-model:generateContent"
    assert "unit-test-key" not in request.full_url
    assert request.get_header("X-goog-api-key") == "unit-test-key"
    body = json.loads(request.data)
    assert len(body["contents"][0]["parts"]) == 7
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert body["generationConfig"]["maxOutputTokens"] == 1500
    assert timeout == 30
    assert result.model_version == "test-version"
    assert result.usage == {"totalTokenCount": 20}


def test_http_error_body_is_never_exposed_or_retried(monkeypatch):
    called = []
    class Opener:
        def open(self, request, timeout):
            called.append(1)
            raise HTTPError(request.full_url, 403, "raw secret message", {}, io.BytesIO(b"sensitive response"))
    monkeypatch.setattr(gemini, "build_opener", lambda *handlers: Opener())
    with pytest.raises(ProviderError) as error:
        call()
    assert str(error.value) == "Provider request failed (HTTP 403); no retry was attempted."
    assert called == [1]


def test_redirect_does_not_forward_credentials():
    assert NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.example") is None


@pytest.mark.parametrize("payload", [
    envelope(candidates=[]),
    envelope(candidates=[{"finishReason": "MAX_TOKENS", "content": {"parts": []}}]),
    envelope(candidates=[{"finishReason": "STOP", "content": {"parts": [{"text": "invalid JSON"}]}}]),
    envelope(modelVersion=None),
])
def test_incomplete_provider_content_is_rejected(monkeypatch, payload):
    setup_fake(monkeypatch, payload)
    with pytest.raises(ProviderError):
        call()


def test_model_url_injection_rejected_before_transport(monkeypatch):
    def forbidden(*args):
        pytest.fail("Invalid model must not reach transport")
    monkeypatch.setattr(gemini, "build_opener", forbidden)
    with pytest.raises(ProviderError):
        generate_content(api_key="unit-key", model="../../bad?key=secret", prompt="", frames=[])
