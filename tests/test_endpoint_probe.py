from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from endpoint_probe import ProbeClassification, probe_openai_compatible_endpoint
from models import InstanceInfo, Provider


def _instance(*, provider: Provider = Provider.DIGITALOCEAN, status: str = "running") -> InstanceInfo:
    return InstanceInfo(
        id="inst-1",
        name="gpu-a",
        provider=provider,
        hardware_slug="gpu-h100x1-80gb",
        model_repo_id="google/gemma-2-2b-it",
        status=status,
        endpoint_url="https://example.test",
        region="test",
    )


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


class _FakeAsyncClient:
    def __init__(self, *, responses: dict[tuple[str, str], _FakeResponse], request_error: Exception | None = None):
        self._responses = responses
        self._request_error = request_error

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def get(self, url, headers=None):
        if self._request_error:
            raise self._request_error
        return self._responses[("GET", url)]

    async def post(self, url, headers=None, json=None, timeout=None):
        if self._request_error:
            raise self._request_error
        return self._responses[("POST", url)]


@pytest.mark.asyncio
async def test_probe_ready_when_health_models_and_smoke_pass():
    inst = _instance()
    responses = {
        ("GET", "https://example.test/health"): _FakeResponse(200),
        ("GET", "https://example.test/v1/models"): _FakeResponse(
            200,
            payload={"data": [{"id": "google/gemma-2-2b-it"}]},
        ),
        ("POST", "https://example.test/v1/chat/completions"): _FakeResponse(
            200,
            payload={"choices": [{"message": {"content": "OK"}}]},
        ),
    }

    with patch("endpoint_probe.httpx.AsyncClient", return_value=_FakeAsyncClient(responses=responses)):
        result = await probe_openai_compatible_endpoint(inst)

    assert result.classification == ProbeClassification.READY
    assert result.health_ok is True
    assert result.models_ok is True
    assert result.smoke_ok is True


@pytest.mark.asyncio
async def test_probe_wrong_model_when_expected_model_missing():
    inst = _instance()
    responses = {
        ("GET", "https://example.test/health"): _FakeResponse(200),
        ("GET", "https://example.test/v1/models"): _FakeResponse(
            200,
            payload={"data": [{"id": "other/model"}]},
        ),
    }

    with patch("endpoint_probe.httpx.AsyncClient", return_value=_FakeAsyncClient(responses=responses)):
        result = await probe_openai_compatible_endpoint(inst)

    assert result.classification == ProbeClassification.WRONG_MODEL


@pytest.mark.asyncio
async def test_probe_marks_unhealthy_when_smoke_prompt_fails():
    inst = _instance()
    responses = {
        ("GET", "https://example.test/health"): _FakeResponse(200),
        ("GET", "https://example.test/v1/models"): _FakeResponse(
            200,
            payload={"data": [{"id": "google/gemma-2-2b-it"}]},
        ),
        ("POST", "https://example.test/v1/chat/completions"): _FakeResponse(
            500,
            text="backend failure",
        ),
    }

    with patch("endpoint_probe.httpx.AsyncClient", return_value=_FakeAsyncClient(responses=responses)):
        result = await probe_openai_compatible_endpoint(inst)

    assert result.classification == ProbeClassification.UNHEALTHY


@pytest.mark.asyncio
async def test_probe_marks_unreachable_on_request_error():
    inst = _instance()
    request_error = httpx.RequestError("timed out", request=httpx.Request("GET", "https://example.test/health"))

    with patch(
        "endpoint_probe.httpx.AsyncClient",
        return_value=_FakeAsyncClient(responses={}, request_error=request_error),
    ):
        result = await probe_openai_compatible_endpoint(inst)

    assert result.classification == ProbeClassification.UNREACHABLE


@pytest.mark.asyncio
async def test_probe_detects_modal_scaled_to_zero():
    inst = _instance(provider=Provider.MODAL)
    responses = {
        ("GET", "https://example.test/health"): _FakeResponse(
            404,
            text="App for invoked web endpoint is stopped",
        ),
    }

    with patch("endpoint_probe.httpx.AsyncClient", return_value=_FakeAsyncClient(responses=responses)):
        result = await probe_openai_compatible_endpoint(inst)

    assert result.classification == ProbeClassification.SCALED_TO_ZERO
