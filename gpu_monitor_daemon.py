"""
Standalone cross-provider GPU monitor daemon.

Run this on an always-on host (for example, a tiny EC2 instance) to send
Telegram alerts and optionally auto-stop long-running GPU instances.
"""

from __future__ import annotations

import asyncio
import logging

from config import settings
from monitor import run_monitor_once, send_monitor_boot_message
from scheduler import schedule_fleet_monitoring

logger = logging.getLogger(__name__)


async def main() -> None:
    if not settings.monitor_enabled:
        raise RuntimeError(
            "GPU monitor is disabled. Set GPU_MONITOR_ENABLED=true in environment."
        )

    await send_monitor_boot_message(host_label="gpu-monitor-daemon")

    # Run once immediately so the first status snapshot is not delayed.
    await run_monitor_once(
        runtime_alert_minutes=settings.monitor_runtime_alert_minutes,
        auto_stop_minutes=settings.monitor_auto_stop_minutes,
    )

    schedule_fleet_monitoring(
        interval_minutes=settings.monitor_interval_minutes,
        runtime_alert_minutes=settings.monitor_runtime_alert_minutes,
        auto_stop_minutes=settings.monitor_auto_stop_minutes,
        readiness_timeout_minutes=settings.monitor_readiness_timeout_minutes,
        stale_after_minutes=settings.monitor_stale_after_minutes,
        unhealthy_auto_stop_minutes=settings.monitor_unhealthy_auto_stop_minutes,
    )

    logger.info(
        "Monitor daemon running: interval=%dmin runtime_alert=%dmin auto_stop=%dmin readiness_timeout=%dmin stale_after=%dmin unhealthy_auto_stop=%dmin",
        settings.monitor_interval_minutes,
        settings.monitor_runtime_alert_minutes,
        settings.monitor_auto_stop_minutes,
        settings.monitor_readiness_timeout_minutes,
        settings.monitor_stale_after_minutes,
        settings.monitor_unhealthy_auto_stop_minutes,
    )
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
