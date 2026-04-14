"""
Test harness — runs the GPU builder skill interactively.
Usage: python main.py
"""

import asyncio

from skill import run_skill


async def main() -> None:
    print("═" * 50)
    print("  GPU Builder Skill — Test Harness")
    print("═" * 50)

    result = await run_skill(
        instance_name="gpu-skill-poc",
        region="us-east-1",
        max_deployment_hours=2,  # short TTL for testing
    )

    print("\n── Result ───────────────────────────────────")
    if result.success and result.instance:
        inst = result.instance
        print(f"  Status       : SUCCESS")
        print(f"  Instance ID  : {inst.id}")
        print(f"  Name         : {inst.name}")
        print(f"  Provider     : {inst.provider.value}")
        print(f"  Hardware     : {inst.hardware_slug}")
        print(f"  Model        : {inst.model_repo_id}")
        print(f"  State        : {inst.status}")
        if inst.endpoint_url:
            print(f"  Endpoint URL : {inst.endpoint_url}")
    else:
        print(f"  Status       : FAILED")
        print(f"  Reason       : {result.message}")
    print("─────────────────────────────────────────────")


if __name__ == "__main__":
    asyncio.run(main())
