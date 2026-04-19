"""
Cross-provider GPU fleet monitoring with Telegram notifications.

Designed to run on a small always-on host (for example, EC2 free-tier) so
alerts continue even when local laptops or ad-hoc agent sessions are offline.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from config import settings
from do_bootstrap import _load_state as _load_do_state
from do_bootstrap import _save_state as _save_do_state
from models import InstanceInfo, Provider
from providers.modal_provider import get_modal_account_gpu_activity
from providers import PROVIDER_MAP

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = {"pending", "initializing", "running"}
FAILURE_STATUSES = {"failed", "error", "degraded", "unreachable", "stopped", "terminated"}
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
        return {"instances": {}, "provider_errors": {}, "provider_account": {}}
    monitor_state.setdefault("instances", {})
    monitor_state.setdefault("provider_errors", {})
    monitor_state.setdefault("provider_account", {})
    return monitor_state


def _save_monitor_state(monitor_state: dict[str, Any]) -> None:
    state = _load_do_state()
    state[STATE_KEY] = monitor_state
    _save_do_state(state)


async def send_telegram_message(text: str) -> bool:
    token = settings.telegram_bot_token.strip()
    chat_id = settings.telegram_chat_id.strip()
    if not token or not chat_id:
        logger.debug("Telegram is not configured; skipping notification.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    async with httpx.AsyncClient(timeout=12) as client:
        resp = await client.post(url, json=payload)
    if resp.status_code >= 400:
        logger.warning("Telegram send failed: status=%s body=%s", resp.status_code, resp.text[:200])
        return False
    return True


def _instance_key(provider: Provider, instance: InstanceInfo) -> str:
    return f"{provider.value}:{instance.id}"


def _fmt_instance(instance: InstanceInfo) -> str:
    url = f" url={instance.endpoint_url}" if instance.endpoint_url else ""
    model = f" model={instance.model_repo_id}" if instance.model_repo_id else ""
    return (
        f"provider={instance.provider.value} name={instance.name} id={instance.id} "
        f"status={instance.status}{model}{url}"
    )


async def _destroy_instance(provider: Provider, instance_id: str) -> tuple[bool, str]:
    provider_cls = PROVIDER_MAP.get(provider)
    if not provider_cls:
        return False, f"provider {provider.value} not registered"
    try:
        ok = await provider_cls().destroy_instance(instance_id)
        return bool(ok), "ok" if ok else "provider returned false"
    except Exception as exc:
        return False, str(exc)


async def run_monitor_once(
    monitored_providers: tuple[Provider, ...] = DEFAULT_MONITORED_PROVIDERS,
    runtime_alert_minutes: int = 120,
    auto_stop_minutes: int = 0,
) -> None:
    """
    Poll configured providers and emit notifications for lifecycle changes.

    runtime_alert_minutes: alert once when active runtime exceeds this age (0 disables).
    auto_stop_minutes: destroy instance when active runtime exceeds this age (0 disables).
    """
    now = _now_utc()
    monitor_state = _load_monitor_state()
    instances_state: dict[str, dict[str, Any]] = monitor_state["instances"]
    provider_errors: dict[str, dict[str, Any]] = monitor_state["provider_errors"]
    provider_account: dict[str, dict[str, Any]] = monitor_state["provider_account"]

    seen_keys: set[str] = set()

    for provider in monitored_providers:
        provider_cls = PROVIDER_MAP.get(provider)
        if not provider_cls:
            continue
        try:
            instances = await provider_cls().list_instances()
            provider_errors.pop(provider.value, None)
        except Exception as exc:
            detail = str(exc)
            prev = provider_errors.get(provider.value, {})
            if prev.get("last_error") != detail:
                await send_telegram_message(
                    f"[gpu-monitor] Provider list failed: provider={provider.value} error={detail}"
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
            if not entry:
                entry = {
                    "provider": provider.value,
                    "instance_id": inst.id,
                    "name": inst.name,
                    "first_seen_at": now.isoformat(),
                    "first_active_at": now.isoformat() if inst.status in ACTIVE_STATUSES else "",
                    "last_status": inst.status,
                    "last_endpoint_url": inst.endpoint_url,
                    "last_seen_at": now.isoformat(),
                    "runtime_alert_sent": False,
                    "auto_stop_triggered": False,
                    "failure_alert_sent": False,
                }
                instances_state[key] = entry
                await send_telegram_message(f"[gpu-monitor] Detected instance: {_fmt_instance(inst)}")
            else:
                if entry.get("last_status") != inst.status:
                    await send_telegram_message(
                        "[gpu-monitor] Status changed: "
                        f"provider={provider.value} name={inst.name} id={inst.id} "
                        f"{entry.get('last_status')} -> {inst.status}"
                    )
                    entry["failure_alert_sent"] = False
                if entry.get("last_endpoint_url", "") != inst.endpoint_url:
                    await send_telegram_message(
                        "[gpu-monitor] Endpoint changed: "
                        f"provider={provider.value} name={inst.name} id={inst.id} "
                        f"url={entry.get('last_endpoint_url', '')} -> {inst.endpoint_url}"
                    )

                entry["last_status"] = inst.status
                entry["last_endpoint_url"] = inst.endpoint_url
                entry["last_seen_at"] = now.isoformat()

                if inst.status in ACTIVE_STATUSES and not entry.get("first_active_at"):
                    entry["first_active_at"] = now.isoformat()
                    entry["runtime_alert_sent"] = False
                    entry["auto_stop_triggered"] = False
                if inst.status not in ACTIVE_STATUSES:
                    entry["first_active_at"] = ""
                    entry["runtime_alert_sent"] = False
                    entry["auto_stop_triggered"] = False

            if inst.status in FAILURE_STATUSES and not entry.get("failure_alert_sent"):
                await send_telegram_message(f"[gpu-monitor] Failure state detected: {_fmt_instance(inst)}")
                entry["failure_alert_sent"] = True

            first_active_at = _parse_dt(entry.get("first_active_at"))
            if first_active_at and inst.status in ACTIVE_STATUSES:
                runtime_minutes = int((now - first_active_at).total_seconds() / 60)

                if runtime_alert_minutes > 0 and runtime_minutes >= runtime_alert_minutes:
                    if not entry.get("runtime_alert_sent"):
                        await send_telegram_message(
                            "[gpu-monitor] Runtime threshold exceeded: "
                            f"{_fmt_instance(inst)} active_minutes={runtime_minutes} "
                            f"threshold={runtime_alert_minutes}"
                        )
                        entry["runtime_alert_sent"] = True

                if auto_stop_minutes > 0 and runtime_minutes >= auto_stop_minutes:
                    if not entry.get("auto_stop_triggered"):
                        ok, detail = await _destroy_instance(provider, inst.id)
                        entry["auto_stop_triggered"] = True
                        await send_telegram_message(
                            "[gpu-monitor] Auto-stop attempted: "
                            f"{_fmt_instance(inst)} active_minutes={runtime_minutes} "
                            f"threshold={auto_stop_minutes} result={'ok' if ok else 'FAILED'} detail={detail}"
                        )

        if provider == Provider.MODAL:
            try:
                summary = await get_modal_account_gpu_activity()
                prev = provider_account.get(provider.value, {})
                if (
                    prev.get("active_gpu_apps") != summary.get("active_gpu_apps")
                    or prev.get("active_gpu_tasks") != summary.get("active_gpu_tasks")
                ):
                    await send_telegram_message(
                        "[gpu-monitor] Modal account-wide GPU summary: "
                        f"active_gpu_apps={summary.get('active_gpu_apps', 0)} "
                        f"active_gpu_tasks={summary.get('active_gpu_tasks', 0)} "
                        f"total_apps={summary.get('total_apps', 0)} "
                        f"stopped_apps={summary.get('stopped_apps', 0)}"
                    )
                provider_account[provider.value] = {
                    **summary,
                    "last_seen_at": now.isoformat(),
                }
            except Exception as exc:
                detail = str(exc)
                prev = provider_account.get(provider.value, {})
                if prev.get("last_error") != detail:
                    await send_telegram_message(
                        f"[gpu-monitor] Modal account-wide check failed: error={detail}"
                    )
                provider_account[provider.value] = {
                    "ok": False,
                    "last_error": detail,
                    "last_seen_at": now.isoformat(),
                }

    stale_keys = [k for k in instances_state if k not in seen_keys]
    for key in stale_keys:
        entry = instances_state[key]
        await send_telegram_message(
            "[gpu-monitor] Instance no longer listed: "
            f"provider={entry.get('provider')} name={entry.get('name')} id={entry.get('instance_id')}"
        )
        del instances_state[key]

    monitor_state["instances"] = instances_state
    monitor_state["provider_errors"] = provider_errors
    monitor_state["provider_account"] = provider_account
    _save_monitor_state(monitor_state)


async def send_monitor_boot_message(host_label: str = "") -> None:
    suffix = f" host={host_label}" if host_label else ""
    await send_telegram_message(f"[gpu-monitor] Monitor started{suffix}")
