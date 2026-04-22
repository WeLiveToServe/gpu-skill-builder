"""Tests for cross-provider fleet monitoring and alert behavior."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock

import pytest

import monitor
from endpoint_probe import ProbeClassification
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


class _ProviderReady:
    async def list_instances(self):
        return [_instance()]

    async def destroy_instance(self, _instance_id: str):
        return True


@pytest.mark.asyncio
async def test_monitor_new_instance_emits_detection_and_readiness(monkeypatch):
    state = {}
    sent = []

    async def _send(event):
        sent.append(event)
        return True

    monkeypatch.setattr(monitor, "_load_do_state", lambda: state.copy())
    monkeypatch.setattr(monitor, "_save_do_state", lambda s: state.update(s))
    monkeypatch.setattr(monitor, "send_monitor_event", _send)
    monkeypatch.setattr(monitor, "PROVIDER_MAP", {Provider.MODAL: _ProviderReady})
    monkeypatch.setattr(
        monitor,
        "probe_openai_compatible_endpoint",
        AsyncMock(return_value=type("Probe", (), {"classification": ProbeClassification.READY, "detail": "ok"})()),
    )

    await monitor.run_monitor_once(monitored_providers=(Provider.MODAL,), runtime_alert_minutes=0, auto_stop_minutes=0)

    event_names = [event.event.value for event in sent]
    assert "instance_detected" in event_names
    assert "readiness_passed" in event_names
    entry = state["gpu_monitor"]["instances"]["modal:inst-1"]
    assert entry["first_ready_at"]
    assert entry["current_probe_classification"] == "ready"


@pytest.mark.asyncio
async def test_monitor_emits_readiness_timeout(monkeypatch):
    now = monitor._now_utc()
    state = {
        "gpu_monitor": {
            "instances": {
                "modal:inst-1": {
                    "provider": "modal",
                    "instance_id": "inst-1",
                    "name": "gpu-a",
                    "first_seen_at": (now - timedelta(minutes=30)).isoformat(),
                    "first_active_at": "",
                    "first_ready_at": "",
                    "first_non_ready_at": "",
                    "last_status": "running",
                    "last_endpoint_url": "https://example.modal.run",
                    "last_seen_at": (now - timedelta(minutes=5)).isoformat(),
                    "last_probe_at": "",
                    "last_successful_probe_at": "",
                    "current_probe_classification": "warming",
                    "current_probe_detail": "",
                    "consecutive_failures": 1,
                    "runtime_alert_sent": False,
                    "auto_stop_triggered": False,
                    "readiness_timeout_sent": False,
                    "stale_alert_sent": False,
                    "unhealthy_auto_stop_triggered": False,
                }
            },
            "provider_errors": {},
        }
    }
    sent = []

    async def _send(event):
        sent.append(event)
        return True

    monkeypatch.setattr(monitor, "_load_do_state", lambda: state.copy())
    monkeypatch.setattr(monitor, "_save_do_state", lambda s: state.update(s))
    monkeypatch.setattr(monitor, "send_monitor_event", _send)
    monkeypatch.setattr(monitor, "PROVIDER_MAP", {Provider.MODAL: _ProviderReady})
    monkeypatch.setattr(
        monitor,
        "probe_openai_compatible_endpoint",
        AsyncMock(return_value=type("Probe", (), {"classification": ProbeClassification.WARMING, "detail": "still warming"})()),
    )

    await monitor.run_monitor_once(monitored_providers=(Provider.MODAL,), runtime_alert_minutes=0, auto_stop_minutes=0)

    assert any(event.event.value == "readiness_timeout" for event in sent)


@pytest.mark.asyncio
async def test_monitor_emits_health_regressed_after_ready(monkeypatch):
    now = monitor._now_utc()
    state = {
        "gpu_monitor": {
            "instances": {
                "modal:inst-1": {
                    "provider": "modal",
                    "instance_id": "inst-1",
                    "name": "gpu-a",
                    "first_seen_at": (now - timedelta(minutes=40)).isoformat(),
                    "first_active_at": (now - timedelta(minutes=40)).isoformat(),
                    "first_ready_at": (now - timedelta(minutes=35)).isoformat(),
                    "first_non_ready_at": "",
                    "last_status": "running",
                    "last_endpoint_url": "https://example.modal.run",
                    "last_seen_at": (now - timedelta(minutes=5)).isoformat(),
                    "last_probe_at": (now - timedelta(minutes=5)).isoformat(),
                    "last_successful_probe_at": (now - timedelta(minutes=5)).isoformat(),
                    "current_probe_classification": "ready",
                    "current_probe_detail": "ok",
                    "consecutive_failures": 0,
                    "runtime_alert_sent": False,
                    "auto_stop_triggered": False,
                    "readiness_timeout_sent": False,
                    "stale_alert_sent": False,
                    "unhealthy_auto_stop_triggered": False,
                }
            },
            "provider_errors": {},
        }
    }
    sent = []

    async def _send(event):
        sent.append(event)
        return True

    monkeypatch.setattr(monitor, "_load_do_state", lambda: state.copy())
    monkeypatch.setattr(monitor, "_save_do_state", lambda s: state.update(s))
    monkeypatch.setattr(monitor, "send_monitor_event", _send)
    monkeypatch.setattr(monitor, "PROVIDER_MAP", {Provider.MODAL: _ProviderReady})
    monkeypatch.setattr(
        monitor,
        "probe_openai_compatible_endpoint",
        AsyncMock(return_value=type("Probe", (), {"classification": ProbeClassification.UNHEALTHY, "detail": "health failed"})()),
    )

    await monitor.run_monitor_once(monitored_providers=(Provider.MODAL,), runtime_alert_minutes=0, auto_stop_minutes=0)

    assert any(event.event.value == "health_regressed" for event in sent)


@pytest.mark.asyncio
async def test_monitor_emits_stale_threshold_alert(monkeypatch):
    now = monitor._now_utc()
    state = {
        "gpu_monitor": {
            "instances": {
                "modal:inst-1": {
                    "provider": "modal",
                    "instance_id": "inst-1",
                    "name": "gpu-a",
                    "first_seen_at": (now - timedelta(minutes=60)).isoformat(),
                    "first_active_at": (now - timedelta(minutes=60)).isoformat(),
                    "first_ready_at": (now - timedelta(minutes=55)).isoformat(),
                    "first_non_ready_at": (now - timedelta(minutes=15)).isoformat(),
                    "last_status": "running",
                    "last_endpoint_url": "https://example.modal.run",
                    "last_seen_at": (now - timedelta(minutes=5)).isoformat(),
                    "last_probe_at": (now - timedelta(minutes=5)).isoformat(),
                    "last_successful_probe_at": (now - timedelta(minutes=20)).isoformat(),
                    "current_probe_classification": "unhealthy",
                    "current_probe_detail": "old failure",
                    "consecutive_failures": 3,
                    "runtime_alert_sent": False,
                    "auto_stop_triggered": False,
                    "readiness_timeout_sent": False,
                    "stale_alert_sent": False,
                    "unhealthy_auto_stop_triggered": False,
                }
            },
            "provider_errors": {},
        }
    }
    sent = []

    async def _send(event):
        sent.append(event)
        return True

    monkeypatch.setattr(monitor, "_load_do_state", lambda: state.copy())
    monkeypatch.setattr(monitor, "_save_do_state", lambda s: state.update(s))
    monkeypatch.setattr(monitor, "send_monitor_event", _send)
    monkeypatch.setattr(monitor, "PROVIDER_MAP", {Provider.MODAL: _ProviderReady})
    monkeypatch.setattr(
        monitor,
        "probe_openai_compatible_endpoint",
        AsyncMock(return_value=type("Probe", (), {"classification": ProbeClassification.UNHEALTHY, "detail": "still bad"})()),
    )

    await monitor.run_monitor_once(monitored_providers=(Provider.MODAL,), runtime_alert_minutes=0, auto_stop_minutes=0)

    assert any(event.event.value == "stale_endpoint" for event in sent)


@pytest.mark.asyncio
async def test_monitor_auto_stop_after_unhealthy_threshold(monkeypatch):
    now = monitor._now_utc()
    state = {
        "gpu_monitor": {
            "instances": {
                "modal:inst-1": {
                    "provider": "modal",
                    "instance_id": "inst-1",
                    "name": "gpu-a",
                    "first_seen_at": (now - timedelta(minutes=120)).isoformat(),
                    "first_active_at": (now - timedelta(minutes=120)).isoformat(),
                    "first_ready_at": (now - timedelta(minutes=115)).isoformat(),
                    "first_non_ready_at": (now - timedelta(minutes=30)).isoformat(),
                    "last_status": "running",
                    "last_endpoint_url": "https://example.modal.run",
                    "last_seen_at": (now - timedelta(minutes=5)).isoformat(),
                    "last_probe_at": (now - timedelta(minutes=5)).isoformat(),
                    "last_successful_probe_at": (now - timedelta(minutes=35)).isoformat(),
                    "current_probe_classification": "unhealthy",
                    "current_probe_detail": "old failure",
                    "consecutive_failures": 4,
                    "runtime_alert_sent": False,
                    "auto_stop_triggered": False,
                    "readiness_timeout_sent": False,
                    "stale_alert_sent": True,
                    "unhealthy_auto_stop_triggered": False,
                }
            },
            "provider_errors": {},
        }
    }
    sent = []
    destroy_mock = AsyncMock(return_value=True)

    async def _send(event):
        sent.append(event)
        return True

    class _ProviderAutoStop:
        async def list_instances(self):
            return [_instance()]

        destroy_instance = destroy_mock

    monkeypatch.setattr(monitor, "_load_do_state", lambda: state.copy())
    monkeypatch.setattr(monitor, "_save_do_state", lambda s: state.update(s))
    monkeypatch.setattr(monitor, "send_monitor_event", _send)
    monkeypatch.setattr(monitor, "PROVIDER_MAP", {Provider.MODAL: _ProviderAutoStop})
    monkeypatch.setattr(
        monitor,
        "probe_openai_compatible_endpoint",
        AsyncMock(return_value=type("Probe", (), {"classification": ProbeClassification.UNHEALTHY, "detail": "still bad"})()),
    )

    await monitor.run_monitor_once(
        monitored_providers=(Provider.MODAL,),
        runtime_alert_minutes=0,
        auto_stop_minutes=0,
        unhealthy_auto_stop_minutes=20,
    )

    destroy_mock.assert_awaited_once()
    assert any(event.event.value == "auto_stop_attempted" for event in sent)


@pytest.mark.asyncio
async def test_provider_list_failure_is_deduped(monkeypatch):
    state = {}
    sent = []

    async def _send(event):
        sent.append(event)
        return True

    class _BrokenProvider:
        async def list_instances(self):
            raise RuntimeError("provider api down")

    monkeypatch.setattr(monitor, "_load_do_state", lambda: state.copy())
    monkeypatch.setattr(monitor, "_save_do_state", lambda s: state.update(s))
    monkeypatch.setattr(monitor, "send_monitor_event", _send)
    monkeypatch.setattr(monitor, "PROVIDER_MAP", {Provider.MODAL: _BrokenProvider})

    await monitor.run_monitor_once(monitored_providers=(Provider.MODAL,), runtime_alert_minutes=0, auto_stop_minutes=0)
    await monitor.run_monitor_once(monitored_providers=(Provider.MODAL,), runtime_alert_minutes=0, auto_stop_minutes=0)

    provider_failures = [event for event in sent if event.event.value == "provider_list_failed"]
    assert len(provider_failures) == 1
