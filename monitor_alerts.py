from __future__ import annotations

import json
from enum import Enum

import httpx
from pydantic import BaseModel

from config import settings


class MonitorEventType(str, Enum):
    MONITOR_STARTED = "monitor_started"
    INSTANCE_DETECTED = "instance_detected"
    READINESS_PASSED = "readiness_passed"
    READINESS_TIMEOUT = "readiness_timeout"
    HEALTH_REGRESSED = "health_regressed"
    STALE_ENDPOINT = "stale_endpoint"
    PROVIDER_LIST_FAILED = "provider_list_failed"
    INSTANCE_DISAPPEARED = "instance_disappeared"
    RUNTIME_THRESHOLD_EXCEEDED = "runtime_threshold_exceeded"
    AUTO_STOP_ATTEMPTED = "auto_stop_attempted"


class MonitorEvent(BaseModel):
    event: MonitorEventType
    provider: str = ""
    instance_id: str = ""
    name: str = ""
    status: str = ""
    model_repo_id: str = ""
    classification: str = ""
    url: str = ""
    detail: str = ""
    active_minutes: int | None = None
    threshold_minutes: int | None = None
    result: str = ""


def _clean_value(value: str) -> str:
    compact = " ".join((value or "").split())
    return compact[:240]


def format_monitor_event(event: MonitorEvent) -> str:
    payload: dict[str, str | int] = {
        "event": event.event.value,
    }
    ordered_values = [
        ("provider", event.provider),
        ("name", event.name),
        ("id", event.instance_id),
        ("status", event.status),
        ("classification", event.classification),
        ("model", event.model_repo_id),
        ("url", event.url),
        ("detail", _clean_value(event.detail)),
    ]
    for key, value in ordered_values:
        if value:
            payload[key] = value
    if event.active_minutes is not None:
        payload["active_minutes"] = event.active_minutes
    if event.threshold_minutes is not None:
        payload["threshold_minutes"] = event.threshold_minutes
    if event.result:
        payload["result"] = event.result
    return f"[gpu-monitor] {json.dumps(payload, separators=(',', ':'))}"


async def send_telegram_message(text: str) -> bool:
    token = settings.telegram_bot_token.strip()
    chat_id = settings.telegram_chat_id.strip()
    if not token or not chat_id:
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    async with httpx.AsyncClient(timeout=12) as client:
        resp = await client.post(url, json=payload)
    return resp.status_code < 400


async def send_monitor_event(event: MonitorEvent) -> bool:
    return await send_telegram_message(format_monitor_event(event))
