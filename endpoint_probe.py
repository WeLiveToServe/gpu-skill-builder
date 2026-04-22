from __future__ import annotations

import json
from enum import Enum

import httpx
from pydantic import BaseModel, Field

from config import settings
from models import InstanceInfo, Provider


class ProbeClassification(str, Enum):
    READY = "ready"
    WARMING = "warming"
    WRONG_MODEL = "wrong_model"
    UNHEALTHY = "unhealthy"
    UNREACHABLE = "unreachable"
    PROVIDER_ERROR = "provider_error"
    SCALED_TO_ZERO = "scaled_to_zero"


class EndpointProbeResult(BaseModel):
    classification: ProbeClassification
    detail: str = ""
    endpoint_url: str = ""
    expected_model_id: str = ""
    served_model_ids: list[str] = Field(default_factory=list)
    health_ok: bool = False
    models_ok: bool = False
    smoke_ok: bool = False
    smoke_model_id: str = ""

    @property
    def is_ready(self) -> bool:
        return self.classification == ProbeClassification.READY


_WARMING_STATUSES = {
    "pending",
    "initializing",
    "deploying",
    "loading",
    "starting",
    "provisioning",
    "building",
    "queued",
    "creating",
    "new",
    "warmup",
}

_TERMINAL_STATUSES = {
    "stopped",
    "terminated",
    "deleted",
}


def _clean_detail(text: str) -> str:
    compact = " ".join((text or "").split())
    return compact[:240]


def status_indicates_warming(status: str) -> bool:
    return status.strip().lower() in _WARMING_STATUSES


def status_indicates_terminal(status: str) -> bool:
    return status.strip().lower() in _TERMINAL_STATUSES


def classification_to_provider_status(classification: ProbeClassification) -> str:
    return {
        ProbeClassification.READY: "running",
        ProbeClassification.WARMING: "initializing",
        ProbeClassification.WRONG_MODEL: "degraded",
        ProbeClassification.UNHEALTHY: "degraded",
        ProbeClassification.UNREACHABLE: "unreachable",
        ProbeClassification.PROVIDER_ERROR: "unreachable",
        ProbeClassification.SCALED_TO_ZERO: "scaled_to_zero",
    }[classification]


def _headers_for_instance(instance: InstanceInfo) -> tuple[dict[str, str], str | None]:
    headers: dict[str, str] = {}
    if instance.provider == Provider.HUGGINGFACE:
        token = settings.hf_token.strip()
        if not token:
            return headers, "HF_TOKEN is required to probe Hugging Face endpoints"
        headers["Authorization"] = f"Bearer {token}"
    return headers, None


def _modal_special_classification(status_code: int, body: str) -> ProbeClassification | None:
    if status_code != 404:
        return None
    body_lc = (body or "").lower()
    if "app for invoked web endpoint is stopped" in body_lc:
        return ProbeClassification.SCALED_TO_ZERO
    if "invalid function call" in body_lc:
        return ProbeClassification.UNHEALTHY
    return None


def _request_error_result(instance: InstanceInfo, exc: httpx.RequestError) -> EndpointProbeResult:
    detail = _clean_detail(str(exc))
    classification = ProbeClassification.WARMING if status_indicates_warming(instance.status) else ProbeClassification.UNREACHABLE
    return EndpointProbeResult(
        classification=classification,
        detail=detail or "request failed",
        endpoint_url=instance.endpoint_url,
        expected_model_id=instance.served_model_name or instance.model_repo_id,
    )


def _response_result(
    instance: InstanceInfo,
    *,
    status_code: int,
    detail: str,
    warming_on_status: set[int] | None = None,
) -> EndpointProbeResult:
    if instance.provider == Provider.MODAL:
        special = _modal_special_classification(status_code, detail)
        if special:
            return EndpointProbeResult(
                classification=special,
                detail=_clean_detail(detail) or f"http {status_code}",
                endpoint_url=instance.endpoint_url,
                expected_model_id=instance.served_model_name or instance.model_repo_id,
            )

    if status_code in {401, 403, 429}:
        classification = ProbeClassification.PROVIDER_ERROR
    elif warming_on_status and status_code in warming_on_status and status_indicates_warming(instance.status):
        classification = ProbeClassification.WARMING
    elif status_indicates_warming(instance.status) and status_code >= 500:
        classification = ProbeClassification.WARMING
    else:
        classification = ProbeClassification.UNHEALTHY

    return EndpointProbeResult(
        classification=classification,
        detail=_clean_detail(detail) or f"http {status_code}",
        endpoint_url=instance.endpoint_url,
        expected_model_id=instance.served_model_name or instance.model_repo_id,
    )


async def probe_openai_compatible_endpoint(
    instance: InstanceInfo,
    *,
    expected_model_id: str | None = None,
    smoke_prompt: str = "Reply with OK",
    health_timeout_seconds: float = 6.0,
    smoke_timeout_seconds: float = 20.0,
) -> EndpointProbeResult:
    expected_model = (expected_model_id or instance.served_model_name or instance.model_repo_id or "").strip()

    if not instance.endpoint_url.strip():
        classification = ProbeClassification.WARMING if status_indicates_warming(instance.status) else ProbeClassification.UNREACHABLE
        return EndpointProbeResult(
            classification=classification,
            detail="endpoint_url missing",
            endpoint_url=instance.endpoint_url,
            expected_model_id=expected_model,
        )

    headers, header_error = _headers_for_instance(instance)
    if header_error:
        return EndpointProbeResult(
            classification=ProbeClassification.PROVIDER_ERROR,
            detail=header_error,
            endpoint_url=instance.endpoint_url,
            expected_model_id=expected_model,
        )

    base = instance.endpoint_url.rstrip("/")

    async with httpx.AsyncClient(timeout=health_timeout_seconds) as client:
        try:
            health_resp = await client.get(f"{base}/health", headers=headers)
        except httpx.RequestError as exc:
            return _request_error_result(instance, exc)

        if health_resp.status_code != 200:
            return _response_result(
                instance,
                status_code=health_resp.status_code,
                detail=health_resp.text,
                warming_on_status={404, 408, 425, 500, 502, 503, 504},
            )

        try:
            models_resp = await client.get(f"{base}/v1/models", headers=headers)
        except httpx.RequestError as exc:
            return _request_error_result(instance, exc)

        if models_resp.status_code != 200:
            result = _response_result(
                instance,
                status_code=models_resp.status_code,
                detail=models_resp.text,
                warming_on_status={404, 408, 500, 502, 503, 504},
            )
            result.health_ok = True
            return result

        try:
            payload = models_resp.json()
        except json.JSONDecodeError:
            return EndpointProbeResult(
                classification=ProbeClassification.UNHEALTHY,
                detail="invalid JSON from /v1/models",
                endpoint_url=instance.endpoint_url,
                expected_model_id=expected_model,
                health_ok=True,
            )

        served_model_ids = [str(item.get("id", "")) for item in payload.get("data", []) if item.get("id")]
        if expected_model and expected_model not in served_model_ids:
            return EndpointProbeResult(
                classification=ProbeClassification.WRONG_MODEL,
                detail=f"expected model {expected_model!r} not in /v1/models",
                endpoint_url=instance.endpoint_url,
                expected_model_id=expected_model,
                served_model_ids=served_model_ids,
                health_ok=True,
                models_ok=True,
            )

        smoke_model_id = expected_model or (served_model_ids[0] if served_model_ids else "")
        if not smoke_model_id:
            return EndpointProbeResult(
                classification=ProbeClassification.WRONG_MODEL,
                detail="no served model IDs returned by /v1/models",
                endpoint_url=instance.endpoint_url,
                expected_model_id=expected_model,
                served_model_ids=served_model_ids,
                health_ok=True,
                models_ok=True,
            )

        smoke_payload = {
            "model": smoke_model_id,
            "messages": [{"role": "user", "content": smoke_prompt}],
            "max_tokens": 8,
            "temperature": 0,
        }

        try:
            smoke_resp = await client.post(
                f"{base}/v1/chat/completions",
                headers=headers,
                json=smoke_payload,
                timeout=smoke_timeout_seconds,
            )
        except httpx.RequestError as exc:
            result = _request_error_result(instance, exc)
            result.health_ok = True
            result.models_ok = True
            result.served_model_ids = served_model_ids
            result.smoke_model_id = smoke_model_id
            return result

        if smoke_resp.status_code != 200:
            result = _response_result(
                instance,
                status_code=smoke_resp.status_code,
                detail=smoke_resp.text,
                warming_on_status={404, 408, 500, 502, 503, 504},
            )
            result.health_ok = True
            result.models_ok = True
            result.served_model_ids = served_model_ids
            result.smoke_model_id = smoke_model_id
            return result

        try:
            smoke_payload = smoke_resp.json()
        except json.JSONDecodeError:
            return EndpointProbeResult(
                classification=ProbeClassification.UNHEALTHY,
                detail="invalid JSON from /v1/chat/completions",
                endpoint_url=instance.endpoint_url,
                expected_model_id=expected_model,
                served_model_ids=served_model_ids,
                health_ok=True,
                models_ok=True,
                smoke_model_id=smoke_model_id,
            )

    choices = smoke_payload.get("choices") or []
    if not choices:
        return EndpointProbeResult(
            classification=ProbeClassification.UNHEALTHY,
            detail="smoke prompt returned no choices",
            endpoint_url=instance.endpoint_url,
            expected_model_id=expected_model,
            served_model_ids=served_model_ids,
            health_ok=True,
            models_ok=True,
            smoke_model_id=smoke_model_id,
        )

    return EndpointProbeResult(
        classification=ProbeClassification.READY,
        detail="health, models, and smoke prompt passed",
        endpoint_url=instance.endpoint_url,
        expected_model_id=expected_model,
        served_model_ids=served_model_ids,
        health_ok=True,
        models_ok=True,
        smoke_ok=True,
        smoke_model_id=smoke_model_id,
    )
