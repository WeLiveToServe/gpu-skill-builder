"""
Programmatic scheduling for GPU instance lifecycle management.
All timing and destruction logic lives here — no LLM involvement.

Jobs:
  - TTL:    auto-destroy an instance after max_deployment_hours
  - Uptime: log instance status on a fixed interval
"""

from __future__ import annotations

from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from models import InstanceInfo, Provider

_scheduler = AsyncIOScheduler()


def _ensure_started() -> None:
    if not _scheduler.running:
        _scheduler.start()


# ── Async job functions ────────────────────────────────────────────────────────

async def _destroy_instance(instance: InstanceInfo) -> None:
    from providers import PROVIDER_MAP

    provider_cls = PROVIDER_MAP.get(instance.provider)
    if not provider_cls:
        print(f"[TTL] Unknown provider for '{instance.name}', skipping destroy.")
        return

    try:
        ok = await provider_cls().destroy_instance(instance.id)
        print(f"[TTL] Auto-destroyed '{instance.name}': {'ok' if ok else 'FAILED'}")
    except Exception as exc:
        print(f"[TTL] Error destroying '{instance.name}': {exc}")


async def _report_uptime(instance: InstanceInfo) -> None:
    from providers import PROVIDER_MAP

    provider_cls = PROVIDER_MAP.get(instance.provider)
    if not provider_cls:
        return

    try:
        current = await provider_cls().get_instance(instance.id)
        print(
            f"[Uptime] '{current.name}'  status={current.status}"
            + (f"  url={current.endpoint_url}" if current.endpoint_url else "")
        )
    except Exception as exc:
        print(f"[Uptime] Could not fetch '{instance.name}': {exc}")


# ── Public API ─────────────────────────────────────────────────────────────────

def schedule_ttl(instance: InstanceInfo, max_hours: int) -> None:
    """Schedule automatic destruction of instance after max_hours."""
    _ensure_started()
    destroy_at = datetime.now() + timedelta(hours=max_hours)
    _scheduler.add_job(
        _destroy_instance,
        trigger=DateTrigger(run_date=destroy_at),
        args=[instance],
        id=f"ttl_{instance.id}",
        replace_existing=True,
    )
    print(f"[Scheduler] TTL scheduled: '{instance.name}' → destroy at {destroy_at:%Y-%m-%d %H:%M:%S}")


def schedule_uptime_report(instance: InstanceInfo, interval_minutes: int) -> None:
    """Schedule periodic status logging for an instance."""
    _ensure_started()
    _scheduler.add_job(
        _report_uptime,
        trigger=IntervalTrigger(minutes=interval_minutes),
        args=[instance],
        id=f"uptime_{instance.id}",
        replace_existing=True,
    )
    print(f"[Scheduler] Uptime reporting every {interval_minutes}min for '{instance.name}'")


def cancel_instance_jobs(instance_id: str) -> None:
    """Cancel both TTL and uptime jobs for a given instance ID."""
    for job_id in (f"ttl_{instance_id}", f"uptime_{instance_id}"):
        job = _scheduler.get_job(job_id)
        if job:
            job.remove()
            print(f"[Scheduler] Cancelled job '{job_id}'")


def get_scheduler() -> AsyncIOScheduler:
    _ensure_started()
    return _scheduler
