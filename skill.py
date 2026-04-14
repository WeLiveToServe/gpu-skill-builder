"""
gpu-builder skill entry point.

Presents an interactive selection flow:
  1. Choose GPU provider
  2. Choose hardware tier
  3. Choose a compatible OS model (deterministic list, no LLM)
  4. Confirm and provision
  5. Programmatically schedule TTL destruction + uptime reporting
"""

from __future__ import annotations

import asyncio

from catalog import get_compatible_models
from config import settings
from models import GpuProvisionRequest, GpuProvisionResult, HardwareTier, ModelRecommendation, Provider
from providers import PROVIDER_MAP


# ── Interactive prompts ────────────────────────────────────────────────────────

def _pick_provider() -> Provider:
    options = list(PROVIDER_MAP.keys())
    print("\nGPU Providers:")
    for i, p in enumerate(options, 1):
        print(f"  {i}. {p.value}")
    while True:
        raw = input("\nSelect provider (number): ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        print("  Invalid — enter a number from the list.")


async def _pick_hardware(provider_key: Provider) -> HardwareTier:
    provider = PROVIDER_MAP[provider_key]()
    hw_list = await provider.list_hardware()
    print(f"\nHardware ({provider_key.value}):")
    for i, hw in enumerate(hw_list, 1):
        print(f"  {i}. {hw.display_name:<32}  {hw.vram_gb:>4} GB VRAM  ${hw.price_per_hour:.2f}/hr")
    while True:
        raw = input("\nSelect hardware (number): ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(hw_list):
            return hw_list[int(raw) - 1]
        print("  Invalid — enter a number from the list.")


def _pick_model(hardware: HardwareTier) -> ModelRecommendation:
    models = get_compatible_models(hardware.vram_gb)
    print(f"\nModels compatible with {hardware.display_name}:")
    for i, m in enumerate(models, 1):
        note = f"  [{m.notes}]" if m.notes else ""
        print(f"  {i}. {m.display_name:<42}  {m.size_params:<8}  ~{m.vram_required_gb} GB{note}")
    while True:
        raw = input("\nSelect model (number): ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(models):
            return models[int(raw) - 1]
        print("  Invalid — enter a number from the list.")


# ── Main skill flow ────────────────────────────────────────────────────────────

async def run_skill(
    instance_name: str = "gpu-skill-instance",
    region: str = "us-east-1",
    max_deployment_hours: int | None = None,
) -> GpuProvisionResult:
    """
    Interactive GPU provisioning skill.
    Safe to call from any harness via asyncio.run(run_skill(...)).
    """
    # Import scheduler here to avoid circular imports at module level
    from scheduler import schedule_ttl, schedule_uptime_report

    max_hours = max_deployment_hours or settings.max_deployment_hours

    provider_key = _pick_provider()
    hardware = await _pick_hardware(provider_key)
    model = _pick_model(hardware)

    print("\n── Summary ──────────────────────────────────")
    print(f"  Provider  : {provider_key.value}")
    print(f"  Hardware  : {hardware.display_name}")
    print(f"  Model     : {model.display_name}  ({model.repo_id})")
    print(f"  Region    : {region}")
    print(f"  TTL       : {max_hours}h  (auto-destroy enforced)")
    print("─────────────────────────────────────────────")

    if input("\nProceed? [y/N]: ").strip().lower() != "y":
        return GpuProvisionResult(success=False, message="Cancelled by user.")

    request = GpuProvisionRequest(
        provider=provider_key,
        hardware_slug=hardware.slug,
        model_repo_id=model.repo_id,
        instance_name=instance_name,
        region=region,
        max_deployment_hours=max_hours,
    )

    print("\nProvisioning instance...")
    try:
        provider = PROVIDER_MAP[provider_key]()
        instance = await provider.create_instance(request)
    except Exception as exc:
        return GpuProvisionResult(success=False, message=f"Provisioning failed: {exc}")

    # Programmatic: schedule TTL + uptime — never delegated to the LLM
    schedule_ttl(instance, max_hours)
    schedule_uptime_report(instance, settings.uptime_report_interval_minutes)

    print(f"\nInstance '{instance.name}' created  [status: {instance.status}]")
    if instance.endpoint_url:
        print(f"Endpoint URL : {instance.endpoint_url}")

    return GpuProvisionResult(success=True, instance=instance, message="Instance created successfully.")
