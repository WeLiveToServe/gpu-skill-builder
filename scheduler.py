"""
Programmatic scheduling for GPU instance lifecycle management.
All timing and destruction logic lives here — no LLM involvement.

Jobs:
  - TTL:      auto-destroy an instance after max_deployment_hours
  - Uptime:   log instance status on a fixed interval
  - Watchdog: destroy instances stuck in pending/initializing beyond a timeout
  - Reconcile: on startup, re-register TTL for any live instances (guards against
               process restarts that would orphan running instances)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

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


def schedule_stuck_watchdog(provider_key: Provider, timeout_minutes: int, check_interval_minutes: int) -> None:
    """
    Periodically destroy instances stuck in pending/initializing beyond timeout_minutes.
    Safe to call multiple times — only registers the job once per provider.
    """
    _ensure_started()
    job_id = f"watchdog_{provider_key.value}"
    if _scheduler.get_job(job_id):
        return
    _scheduler.add_job(
        _watchdog_stuck_pending,
        trigger=IntervalTrigger(minutes=check_interval_minutes),
        args=[provider_key, timeout_minutes],
        id=job_id,
    )
    print(
        f"[Scheduler] Stuck-pending watchdog active for {provider_key.value} "
        f"(timeout={timeout_minutes}min, checks every {check_interval_minutes}min)"
    )


async def reconcile_on_startup(provider_key: Provider, fallback_ttl_hours: int = 1) -> None:
    """
    Call once at process startup to re-register TTL jobs for any live instances.

    Guards against the case where this process previously died and left instances
    running with no in-memory TTL job to destroy them.  Since we don't persist the
    original creation time, we schedule a conservative fallback TTL from *now*.
    """
    from providers import PROVIDER_MAP

    provider = PROVIDER_MAP[provider_key]()
    try:
        instances = await provider.list_instances()
    except Exception as exc:
        print(f"[Reconcile] Could not list {provider_key.value} instances: {exc}")
        return

    active_statuses = {"pending", "initializing", "running"}
    orphans = [i for i in instances if i.status in active_statuses]

    if not orphans:
        return

    print(f"[Reconcile] Found {len(orphans)} live instance(s) on startup — re-registering TTL jobs.")
    for inst in orphans:
        # Only re-register if there is no existing TTL job (i.e. process was restarted)
        if _scheduler.get_job(f"ttl_{inst.id}"):
            continue
        destroy_at = datetime.now() + timedelta(hours=fallback_ttl_hours)
        _scheduler.add_job(
            _destroy_instance,
            trigger=DateTrigger(run_date=destroy_at),
            args=[inst],
            id=f"ttl_{inst.id}",
            replace_existing=True,
        )
        print(
            f"[Reconcile] Re-registered TTL for orphaned instance '{inst.name}' "
            f"(status={inst.status}) → destroy at {destroy_at:%H:%M:%S} "
            f"(fallback {fallback_ttl_hours}h from now)"
        )


# ── Internal watchdog job ──────────────────────────────────────────────────────

async def _watchdog_stuck_pending(provider_key: Provider, timeout_minutes: int) -> None:
    from providers import PROVIDER_MAP

    provider = PROVIDER_MAP[provider_key]()
    try:
        instances = await provider.list_instances()
    except Exception as exc:
        print(f"[Watchdog] Could not list instances for {provider_key.value}: {exc}")
        return

    now = datetime.now(tz=timezone.utc)
    for inst in instances:
        if inst.status not in ("pending", "initializing"):
            continue
        if not inst.created_at:
            continue
        try:
            created = datetime.fromisoformat(inst.created_at.replace("Z", "+00:00"))
            age_minutes = (now - created).total_seconds() / 60
        except ValueError:
            continue

        if age_minutes >= timeout_minutes:
            print(
                f"[Watchdog] '{inst.name}' stuck in '{inst.status}' for {age_minutes:.0f}min "
                f"(limit={timeout_minutes}min) — destroying."
            )
            try:
                await provider.destroy_instance(inst.id)
                cancel_instance_jobs(inst.id)
            except Exception as exc:
                print(f"[Watchdog] Failed to destroy '{inst.name}': {exc}")


def get_scheduler() -> AsyncIOScheduler:
    _ensure_started()
    return _scheduler
