"""
Test harness — provisions a T4 + Gemma 2 2B in agent mode, then polls until running.
Usage: python main.py
"""

import asyncio

from providers import PROVIDER_MAP
from models import Provider
from scheduler import reconcile_on_startup
from skill import run_skill

POLL_INTERVAL_SECONDS = 15
POLL_TIMEOUT_SECONDS = 600  # 10 minutes


async def poll_until_running(instance_id: str) -> None:
    provider = PROVIDER_MAP[Provider.HUGGINGFACE]()
    print(f"\nPolling for 'running' state (every {POLL_INTERVAL_SECONDS}s, timeout {POLL_TIMEOUT_SECONDS // 60}m)...")
    elapsed = 0
    while elapsed < POLL_TIMEOUT_SECONDS:
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
        elapsed += POLL_INTERVAL_SECONDS
        try:
            inst = await provider.get_instance(instance_id)
        except Exception as exc:
            print(f"  [{elapsed:>4}s] poll error: {exc}")
            continue

        print(f"  [{elapsed:>4}s] state={inst.status}")
        if inst.status == "running":
            print(f"\n  Endpoint ready: {inst.endpoint_url}")
            return
        if inst.status in ("failed", "error"):
            print(f"\n  Instance entered error state: {inst.status}")
            return

    print("\n  Timed out waiting for running state.")


async def main() -> None:
    print("=" * 50)
    print("  GPU Builder Skill — Test Harness")
    print("=" * 50)

    # Startup reconciliation — re-registers TTL for any instances left running
    # from a previous process run (guards against orphaned instances on restart)
    await reconcile_on_startup(Provider.HUGGINGFACE)

    result = await run_skill(
        instance_name="gpu-skill-poc",
        region="us-east-1",
        max_deployment_hours=2,
        provider="huggingface",
        hardware_slug="nvidia-t4-x1",
        model_repo_id="google/gemma-2-2b-it",
    )

    print("\n── Provision Result ─────────────────────────")
    if result.success and result.instance:
        inst = result.instance
        print(f"  Status       : SUCCESS")
        print(f"  Instance ID  : {inst.id}")
        print(f"  Provider     : {inst.provider.value}")
        print(f"  Hardware     : {inst.hardware_slug}")
        print(f"  Model        : {inst.model_repo_id}")
        print(f"  State        : {inst.status}")
        if inst.endpoint_url:
            print(f"  Endpoint URL : {inst.endpoint_url}")
        print("─────────────────────────────────────────────")

        if inst.status != "running":
            await poll_until_running(inst.id)
    else:
        print(f"  Status       : FAILED")
        print(f"  Reason       : {result.message}")
        print("─────────────────────────────────────────────")


if __name__ == "__main__":
    asyncio.run(main())
