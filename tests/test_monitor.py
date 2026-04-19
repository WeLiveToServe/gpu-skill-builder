"""Tests for cross-provider fleet monitoring and alert behavior."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock

import pytest

import monitor
from models import InstanceInfo, Provider


def _instance(
    *,
    instance_id: str = "inst-1",
    name: str = "gpu-a",
    status: str = "running",
    provider: Provider = Provider.MODAL,
    endpoint_url: str = "https://example.modal.run",
) -> InstanceInfo:
    return InstanceInfo(
        id=instance_id,
        name=name,
        provider=provider,
        hardware_slug="H100",
        model_repo_id="openai/gpt-oss-120b",
        status=status,
        endpoint_url=endpoint_url,
        region="test",
    )


class _ProviderOne:
    async def list_instances(self):
        return [_instance()]

    async def destroy_instance(self, _instance_id: str):
        return True


class _ProviderChanged:
    async def list_instances(self):
        return [_instance(status="degraded")]

    async def destroy_instance(self, _instance_id: str):
        return True


@pytest.mark.asyncio
async def test_monitor_new_instance_emits_detection_and_saves_state(monkeypatch):
    state = {}
    monkeypatch.setattr(monitor, "_load_do_state", lambda: state.copy())
    monkeypatch.setattr(monitor, "_save_do_state", lambda s: state.update(s))
    sent = []

    async def _send(msg: str):
        sent.append(msg)
        return True

    monkeypatch.setattr(monitor, "send_telegram_message", _send)
    monkeypatch.setattr(monitor, "PROVIDER_MAP", {Provider.MODAL: _ProviderOne})

    await monitor.run_monitor_once(monitored_providers=(Provider.MODAL,), runtime_alert_minutes=0, auto_stop_minutes=0)

    assert any("Detected instance" in m for m in sent)
    monitor_state = state.get("gpu_monitor", {})
    assert "instances" in monitor_state
    assert any(k.startswith("modal:") for k in monitor_state["instances"].keys())


@pytest.mark.asyncio
async def test_monitor_status_change_and_failure_alert(monkeypatch):
    now = monitor._now_utc()
    key = "modal:inst-1"
    state = {
        "gpu_monitor": {
            "instances": {
                key: {
                    "provider": "modal",
                    "instance_id": "inst-1",
                    "name": "gpu-a",
                    "first_seen_at": (now - timedelta(minutes=30)).isoformat(),
                    "first_active_at": (now - timedelta(minutes=30)).isoformat(),
                    "last_status": "running",
                    "last_endpoint_url": "https://example.modal.run",
                    "last_seen_at": (now - timedelta(minutes=5)).isoformat(),
                    "runtime_alert_sent": False,
                    "auto_stop_triggered": False,
                    "failure_alert_sent": False,
                }
            },
            "provider_errors": {},
        }
    }
    monkeypatch.setattr(monitor, "_load_do_state", lambda: state.copy())
    monkeypatch.setattr(monitor, "_save_do_state", lambda s: state.update(s))
    sent = []

    async def _send(msg: str):
        sent.append(msg)
        return True

    monkeypatch.setattr(monitor, "send_telegram_message", _send)
    monkeypatch.setattr(monitor, "PROVIDER_MAP", {Provider.MODAL: _ProviderChanged})

    await monitor.run_monitor_once(monitored_providers=(Provider.MODAL,), runtime_alert_minutes=0, auto_stop_minutes=0)

    assert any("Status changed" in m for m in sent)
    assert any("Failure state detected" in m for m in sent)


@pytest.mark.asyncio
async def test_monitor_auto_stop_after_runtime_threshold(monkeypatch):
    now = monitor._now_utc()
    key = "modal:inst-1"
    state = {
        "gpu_monitor": {
            "instances": {
                key: {
                    "provider": "modal",
                    "instance_id": "inst-1",
                    "name": "gpu-a",
                    "first_seen_at": (now - timedelta(minutes=120)).isoformat(),
                    "first_active_at": (now - timedelta(minutes=120)).isoformat(),
                    "last_status": "running",
                    "last_endpoint_url": "https://example.modal.run",
                    "last_seen_at": (now - timedelta(minutes=5)).isoformat(),
                    "runtime_alert_sent": False,
                    "auto_stop_triggered": False,
                    "failure_alert_sent": False,
                }
            },
            "provider_errors": {},
        }
    }
    monkeypatch.setattr(monitor, "_load_do_state", lambda: state.copy())
    monkeypatch.setattr(monitor, "_save_do_state", lambda s: state.update(s))
    sent = []

    async def _send(msg: str):
        sent.append(msg)
        return True

    destroy_mock = AsyncMock(return_value=True)

    class _ProviderAutoStop:
        async def list_instances(self):
            return [_instance()]

        destroy_instance = destroy_mock

    monkeypatch.setattr(monitor, "send_telegram_message", _send)
    monkeypatch.setattr(monitor, "PROVIDER_MAP", {Provider.MODAL: _ProviderAutoStop})

    await monitor.run_monitor_once(monitored_providers=(Provider.MODAL,), runtime_alert_minutes=30, auto_stop_minutes=60)

    destroy_mock.assert_awaited_once()
    assert any("Auto-stop attempted" in m for m in sent)
