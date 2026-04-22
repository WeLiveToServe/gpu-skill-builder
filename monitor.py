"""
Cross-provider GPU fleet monitoring with deterministic Telegram notifications.

Designed to run on a small always-on host so alerts continue even when local
laptops or short-lived agent sessions are offline.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from config import settings
from do_bootstrap import _load_state as _load_do_state
from do_bootstrap import _save_state as _save_do_state
from endpoint_probe import ProbeClassification, probe_openai_compatible_endpoint
from monitor_alerts import MonitorEvent, MonitorEventType, send_monitor_event, send_telegram_message
from models import InstanceInfo, Provider
from providers import PROVIDER_MAP

logger = logging.getLogger(__name__)

DEFAULT_MONITORED_PROVIDERS = (Provider.HUGGINGFACE, Provider.MODAL, Provider.DIGITALOCEAN)
STATE_KEY = "gpu_monitor"


def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def _parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _load_monitor_state() -> dict[str, Any]:
    state = _load_do_state()
    monitor_state = state.get(STATE_KEY, {})
    if not isinstance(monitor_state, dict):
        return {"instances": {}, "provider_errors": {}}
    monitor_state.setdefault("instances", {})
    monitor_state.setdefault("provider_errors", {})
    return monitor_state


def _save_monitor_state(monitor_state: dict[str, Any]) -> None:
    state = _load_do_state()
    state[STATE_KEY] = monitor_state
    _save_do_state(state)


def _instance_key(provider: Provider, instance: InstanceInfo) -> str:
    return f"{provider.value}:{instance.id}"


async def _destroy_instance(provider: Provider, instance_id: str) -> tuple[bool, str]:
    provider_cls = PROVIDER_MAP.get(provider)
    if not provider_cls:
        return False, f"provider {provider.value} not registered"
    try:
        ok = await provider_cls().destroy_instance(instance_id)
        return bool(ok), "ok" if ok else "provider returned false"
    except Exception as exc:
        return False, str(exc)


def _new_instance_entry(provider: Provider, instance: InstanceInfo, now: datetime) -> dict[str, Any]:
    return {
        "provider": provider.value,
        "instance_id": instance.id,
        "name": instance.name,
        "first_seen_at": now.isoformat(),
        "first_active_at": "",
        "first_ready_at": "",
        "first_non_ready_at": "",
        "last_status": instance.status,
        "last_endpoint_url": instance.endpoint_url,
        "last_seen_at": now.isoformat(),
        "last_probe_at": "",
        "last_successful_probe_at": "",
        "current_probe_classification": "",
        "current_probe_detail": "",
        "consecutive_failures": 0,
        "runtime_alert_sent": False,
        "auto_stop_triggered": False,
        "readiness_timeout_sent": False,
        "stale_alert_sent": False,
        "unhealthy_auto_stop_triggered": False,
    }


def _minutes_since(raw: str | None, now: datetime) -> int | None:
    parsed = _parse_dt(raw)
    if not parsed:
        return None
    return int((now - parsed).total_seconds() / 60)


def _runtime_active(instance: InstanceInfo, classification: ProbeClassification) -> bool:
    if classification == ProbeClassification.SCALED_TO_ZERO:
        return False
    return instance.status not in {"stopped", "terminated", "deleted"}


def _non_ready_candidate(classification: ProbeClassification) -> bool:
    return classification not in {ProbeClassification.READY, ProbeClassification.SCALED_TO_ZERO}


async def _emit_event(
    event_type: MonitorEventType,
    instance: InstanceInfo | None = None,
    *,
    provider: Provider | None = None,
    instance_id: str = "",
    name: str = "",
    status: str = "",
    model_repo_id: str = "",
    endpoint_url: str = "",
    classification: str = "",
    detail: str = "",
    active_minutes: int | None = None,
    threshold_minutes: int | None = None,
    result: str = "",
) -> None:
    if instance is not None:
        provider = instance.provider
        instance_id = instance.id
        name = instance.name
        status = instance.status
        model_repo_id = instance.model_repo_id
        endpoint_url = instance.endpoint_url
    await send_monitor_event(
        MonitorEvent(
            event=event_type,
            provider=provider.value if provider else "",
            instance_id=instance_id,
            name=name,
            status=status,
            model_repo_id=model_repo_id,
            classification=classification,
            url=endpoint_url,
            detail=detail,
            active_minutes=active_minutes,
            threshold_minutes=threshold_minutes,
            result=result,
        )
    )


async def _apply_probe_result(
    instance: InstanceInfo,
    entry: dict[str, Any],
    probe_classification: ProbeClassification,
    probe_detail: str,
    now: datetime,
    *,
    runtime_alert_minutes: int,
    auto_stop_minutes: int,
    readiness_timeout_minutes: int,
    stale_after_minutes: int,
    unhealthy_auto_stop_minutes: int,
) -> bool:
    prev_classification = entry.get("current_probe_classification", "")
    had_ready_transition = bool(entry.get("first_ready_at"))

    entry["name"] = instance.name
    entry["last_status"] = instance.status
    entry["last_endpoint_url"] = instance.endpoint_url
    entry["last_seen_at"] = now.isoformat()
    entry["last_probe_at"] = now.isoformat()
    entry["current_probe_classification"] = probe_classification.value
    entry["current_probe_detail"] = probe_detail

    runtime_active = _runtime_active(instance, probe_classification)
    if runtime_active:
        if not entry.get("first_active_at"):
            entry["first_active_at"] = now.isoformat()
    else:
        entry["first_active_at"] = ""
        entry["runtime_alert_sent"] = False
        entry["auto_stop_triggered"] = False

    if probe_classification == ProbeClassification.READY:
        entry["last_successful_probe_at"] = now.isoformat()
        entry["consecutive_failures"] = 0
        entry["first_non_ready_at"] = ""
        entry["stale_alert_sent"] = False
        entry["unhealthy_auto_stop_triggered"] = False
        if not entry.get("first_ready_at"):
            entry["first_ready_at"] = now.isoformat()
            await _emit_event(
                MonitorEventType.READINESS_PASSED,
                instance,
                classification=probe_classification.value,
                detail=probe_detail,
            )
        elif prev_classification != ProbeClassification.READY.value:
            await _emit_event(
                MonitorEventType.READINESS_PASSED,
                instance,
                classification=probe_classification.value,
                detail=probe_detail,
            )
    else:
        if _non_ready_candidate(probe_classification):
            entry["consecutive_failures"] = int(entry.get("consecutive_failures", 0)) + 1
            if had_ready_transition and not entry.get("first_non_ready_at"):
                entry["first_non_ready_at"] = now.isoformat()
        else:
            entry["consecutive_failures"] = 0
            entry["first_non_ready_at"] = ""

        if prev_classification == ProbeClassification.READY.value:
            await _emit_event(
                MonitorEventType.HEALTH_REGRESSED,
                instance,
                classification=probe_classification.value,
                detail=probe_detail,
            )

        if not had_ready_transition and not entry.get("readiness_timeout_sent"):
            ready_age_minutes = _minutes_since(entry.get("first_seen_at"), now)
            if ready_age_minutes is not None and ready_age_minutes >= readiness_timeout_minutes:
                await _emit_event(
                    MonitorEventType.READINESS_TIMEOUT,
                    instance,
                    classification=probe_classification.value,
                    detail=probe_detail,
                    active_minutes=ready_age_minutes,
                    threshold_minutes=readiness_timeout_minutes,
                )
                entry["readiness_timeout_sent"] = True

        if had_ready_transition and _non_ready_candidate(probe_classification):
            non_ready_minutes = _minutes_since(entry.get("first_non_ready_at"), now)
            if non_ready_minutes is not None and non_ready_minutes >= stale_after_minutes and not entry.get("stale_alert_sent"):
                await _emit_event(
                    MonitorEventType.STALE_ENDPOINT,
                    instance,
                    classification=probe_classification.value,
                    detail=probe_detail,
                    active_minutes=non_ready_minutes,
                    threshold_minutes=stale_after_minutes,
                )
                entry["stale_alert_sent"] = True

            if (
                unhealthy_auto_stop_minutes > 0
                and non_ready_minutes is not None
                and non_ready_minutes >= unhealthy_auto_stop_minutes
                and not entry.get("unhealthy_auto_stop_triggered")
            ):
                ok, destroy_detail = await _destroy_instance(instance.provider, instance.id)
                entry["unhealthy_auto_stop_triggered"] = True
                await _emit_event(
                    MonitorEventType.AUTO_STOP_ATTEMPTED,
                    instance,
                    classification=probe_classification.value,
                    detail=f"reason=stale_or_unhealthy {destroy_detail}",
                    active_minutes=non_ready_minutes,
                    threshold_minutes=unhealthy_auto_stop_minutes,
                    result="ok" if ok else "FAILED",
                )

    active_minutes = _minutes_since(entry.get("first_active_at"), now)
    if runtime_active and active_minutes is not None:
        if runtime_alert_minutes > 0 and active_minutes >= runtime_alert_minutes and not entry.get("runtime_alert_sent"):
            await _emit_event(
                MonitorEventType.RUNTIME_THRESHOLD_EXCEEDED,
                instance,
                classification=probe_classification.value,
                detail=probe_detail,
                active_minutes=active_minutes,
                threshold_minutes=runtime_alert_minutes,
            )
            entry["runtime_alert_sent"] = True

        if auto_stop_minutes > 0 and active_minutes >= auto_stop_minutes and not entry.get("auto_stop_triggered"):
            ok, destroy_detail = await _destroy_instance(instance.provider, instance.id)
            entry["auto_stop_triggered"] = True
            await _emit_event(
                MonitorEventType.AUTO_STOP_ATTEMPTED,
                instance,
                classification=probe_classification.value,
                detail=f"reason=runtime_limit {destroy_detail}",
                active_minutes=active_minutes,
                threshold_minutes=auto_stop_minutes,
                result="ok" if ok else "FAILED",
            )

    return not entry.get("first_ready_at") and not entry.get("readiness_timeout_sent")


async def _process_instance(
    instance: InstanceInfo,
    entry: dict[str, Any],
    now: datetime,
    *,
    runtime_alert_minutes: int,
    auto_stop_minutes: int,
    readiness_timeout_minutes: int,
    stale_after_minutes: int,
    unhealthy_auto_stop_minutes: int,
    emit_detected: bool,
) -> bool:
    probe = await probe_openai_compatible_endpoint(instance, expected_model_id=instance.model_repo_id or None)
    if emit_detected:
        await _emit_event(
            MonitorEventType.INSTANCE_DETECTED,
            instance,
            classification=probe.classification.value,
            detail=probe.detail,
        )
    return await _apply_probe_result(
        instance,
        entry,
        probe.classification,
        probe.detail,
        now,
        runtime_alert_minutes=runtime_alert_minutes,
        auto_stop_minutes=auto_stop_minutes,
        readiness_timeout_minutes=readiness_timeout_minutes,
        stale_after_minutes=stale_after_minutes,
        unhealthy_auto_stop_minutes=unhealthy_auto_stop_minutes,
    )


def _is_missing_instance_error(exc: Exception) -> bool:
    try:
        import httpx

        if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 404:
            return True
    except ImportError:
        pass
    detail = str(exc).lower()
    return "not found" in detail or "no modal app" in detail


async def run_monitor_once(
    monitored_providers: tuple[Provider, ...] = DEFAULT_MONITORED_PROVIDERS,
    runtime_alert_minutes: int = 120,
    auto_stop_minutes: int = 0,
    readiness_timeout_minutes: int | None = None,
    stale_after_minutes: int | None = None,
    unhealthy_auto_stop_minutes: int | None = None,
) -> None:
    """
    Poll configured providers and emit notifications for lifecycle changes.

    runtime_alert_minutes: alert once when active runtime exceeds this age (0 disables).
    auto_stop_minutes: destroy instance when active runtime exceeds this age (0 disables).
    """
    readiness_timeout_minutes = (
        settings.monitor_readiness_timeout_minutes
        if readiness_timeout_minutes is None
        else readiness_timeout_minutes
    )
    stale_after_minutes = settings.monitor_stale_after_minutes if stale_after_minutes is None else stale_after_minutes
    unhealthy_auto_stop_minutes = (
        settings.monitor_unhealthy_auto_stop_minutes
        if unhealthy_auto_stop_minutes is None
        else unhealthy_auto_stop_minutes
    )

    now = _now_utc()
    monitor_state = _load_monitor_state()
    instances_state: dict[str, dict[str, Any]] = monitor_state["instances"]
    provider_errors: dict[str, dict[str, Any]] = monitor_state["provider_errors"]

    seen_keys: set[str] = set()
    listed_provider_values: set[str] = set()

    for provider in monitored_providers:
        provider_cls = PROVIDER_MAP.get(provider)
        if not provider_cls:
            continue
        try:
            instances = await provider_cls().list_instances()
            provider_errors.pop(provider.value, None)
            listed_provider_values.add(provider.value)
        except Exception as exc:
            detail = str(exc)
            prev = provider_errors.get(provider.value, {})
            if prev.get("last_error") != detail:
                await _emit_event(
                    MonitorEventType.PROVIDER_LIST_FAILED,
                    provider=provider,
                    detail=detail,
                )
            provider_errors[provider.value] = {
                "last_error": detail,
                "last_seen_at": now.isoformat(),
            }
            continue

        for inst in instances:
            key = _instance_key(provider, inst)
            seen_keys.add(key)
            entry = instances_state.get(key)
            is_new = entry is None
            if not entry:
                entry = _new_instance_entry(provider, inst, now)
                instances_state[key] = entry
            continue_watch = await _process_instance(
                inst,
                entry,
                now,
                runtime_alert_minutes=runtime_alert_minutes,
                auto_stop_minutes=auto_stop_minutes,
                readiness_timeout_minutes=readiness_timeout_minutes,
                stale_after_minutes=stale_after_minutes,
                unhealthy_auto_stop_minutes=unhealthy_auto_stop_minutes,
                emit_detected=is_new,
            )
            if continue_watch:
                from scheduler import schedule_readiness_watch

                schedule_readiness_watch(
                    inst,
                    poll_seconds=settings.monitor_readiness_poll_seconds,
                    runtime_alert_minutes=runtime_alert_minutes,
                    auto_stop_minutes=auto_stop_minutes,
                    readiness_timeout_minutes=readiness_timeout_minutes,
                    stale_after_minutes=stale_after_minutes,
                    unhealthy_auto_stop_minutes=unhealthy_auto_stop_minutes,
                )

    stale_keys = [
        key
        for key, entry in instances_state.items()
        if entry.get("provider") in listed_provider_values and key not in seen_keys
    ]
    for key in stale_keys:
        entry = instances_state[key]
        await _emit_event(
            MonitorEventType.INSTANCE_DISAPPEARED,
            provider=Provider(entry.get("provider")),
            instance_id=entry.get("instance_id", ""),
            name=entry.get("name", ""),
            status=entry.get("last_status", ""),
            classification=entry.get("current_probe_classification", ""),
            detail="instance no longer listed by provider",
            endpoint_url=entry.get("last_endpoint_url", ""),
        )
        from scheduler import cancel_readiness_watch

        cancel_readiness_watch(Provider(entry.get("provider")), entry.get("instance_id", ""))
        del instances_state[key]

    monitor_state["instances"] = instances_state
    monitor_state["provider_errors"] = provider_errors
    _save_monitor_state(monitor_state)


async def monitor_instance_once(
    provider: Provider,
    instance_id: str,
    *,
    runtime_alert_minutes: int,
    auto_stop_minutes: int,
    readiness_timeout_minutes: int | None = None,
    stale_after_minutes: int | None = None,
    unhealthy_auto_stop_minutes: int | None = None,
) -> bool:
    readiness_timeout_minutes = (
        settings.monitor_readiness_timeout_minutes
        if readiness_timeout_minutes is None
        else readiness_timeout_minutes
    )
    stale_after_minutes = settings.monitor_stale_after_minutes if stale_after_minutes is None else stale_after_minutes
    unhealthy_auto_stop_minutes = (
        settings.monitor_unhealthy_auto_stop_minutes
        if unhealthy_auto_stop_minutes is None
        else unhealthy_auto_stop_minutes
    )

    provider_cls = PROVIDER_MAP.get(provider)
    if not provider_cls:
        return False

    monitor_state = _load_monitor_state()
    instances_state: dict[str, dict[str, Any]] = monitor_state["instances"]
    now = _now_utc()
    key = f"{provider.value}:{instance_id}"

    try:
        instance = await provider_cls().get_instance(instance_id)
    except Exception as exc:
        if _is_missing_instance_error(exc):
            entry = instances_state.pop(key, None)
            if entry:
                await _emit_event(
                    MonitorEventType.INSTANCE_DISAPPEARED,
                    provider=provider,
                    instance_id=entry.get("instance_id", instance_id),
                    name=entry.get("name", ""),
                    status=entry.get("last_status", ""),
                    classification=entry.get("current_probe_classification", ""),
                    detail="instance not found during readiness watch",
                    endpoint_url=entry.get("last_endpoint_url", ""),
                )
            _save_monitor_state(monitor_state)
            from scheduler import cancel_readiness_watch

            cancel_readiness_watch(provider, instance_id)
            return False
        logger.warning("[gpu-monitor] Single-instance check failed for %s/%s: %s", provider.value, instance_id, exc)
        return True

    entry = instances_state.get(key)
    is_new = entry is None
    if not entry:
        entry = _new_instance_entry(provider, instance, now)
        instances_state[key] = entry

    continue_watch = await _process_instance(
        instance,
        entry,
        now,
        runtime_alert_minutes=runtime_alert_minutes,
        auto_stop_minutes=auto_stop_minutes,
        readiness_timeout_minutes=readiness_timeout_minutes,
        stale_after_minutes=stale_after_minutes,
        unhealthy_auto_stop_minutes=unhealthy_auto_stop_minutes,
        emit_detected=is_new,
    )

    monitor_state["instances"] = instances_state
    _save_monitor_state(monitor_state)

    if not continue_watch:
        from scheduler import cancel_readiness_watch

        cancel_readiness_watch(provider, instance_id)
    return continue_watch


async def send_monitor_boot_message(host_label: str = "") -> None:
    detail = f"host={host_label}" if host_label else ""
    await _emit_event(MonitorEventType.MONITOR_STARTED, detail=detail)
