"""
gpu-builder skill entry point.

Two modes:

  Agent mode  — pass provider, hardware_slug, and model_repo_id; no prompts, no
                confirmation. Intended for programmatic / LLM-agent callers.

                result = await run_skill(
                    provider="huggingface",
                    hardware_slug="nvidia-t4-x1",
                    model_repo_id="google/gemma-2-2b-it",
                )

  Interactive mode — omit those three params; presents a deterministic 3-step
                     selection flow and asks for confirmation before provisioning.
"""

from __future__ import annotations

import httpx

from catalog import get_compatible_models
from config import settings
from models import GpuProvisionRequest, GpuProvisionResult, HardwareTier, InstanceInfo, ModelRecommendation, Provider
from providers import PROVIDER_MAP

ACTIVE_STATUSES = {"pending", "initializing", "running", "deployed"}


# ── Interactive prompts ────────────────────────────────────────────────────────

def _pick_provider() -> Provider:
    options = [p for p in PROVIDER_MAP.keys() if p != Provider.OPENROUTER]
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


# ── Agent mode helpers ─────────────────────────────────────────────────────────

async def _resolve_hardware(provider_key: Provider, hardware_slug: str) -> HardwareTier:
    hw_list = await PROVIDER_MAP[provider_key]().list_hardware()
    for hw in hw_list:
        if hw.slug == hardware_slug:
            return hw
    available = ", ".join(h.slug for h in hw_list)
    raise ValueError(f"Unknown hardware slug '{hardware_slug}' for {provider_key.value}. Available: {available}")


def _resolve_model(hardware: HardwareTier, model_repo_id: str) -> ModelRecommendation:
    models = get_compatible_models(hardware.vram_gb)
    for m in models:
        if m.repo_id == model_repo_id:
            return m
    available = ", ".join(m.repo_id for m in models)
    raise ValueError(
        f"Model '{model_repo_id}' not in catalog for {hardware.vram_gb} GB VRAM. "
        f"Compatible models: {available}"
    )


def _openrouter_instance(instance_name: str) -> InstanceInfo:
    return InstanceInfo(
        id=f"{instance_name}-openrouter-fallback",
        name=instance_name,
        provider=Provider.OPENROUTER,
        hardware_slug="openrouter-default",
        model_repo_id=settings.openrouter_model,
        status="running",
        endpoint_url=settings.openrouter_base_url.rstrip("/"),
        region="global",
    )


def _fallback_result(
    instance_name: str,
    reason: str,
    primary_provider_error: str | None = None,
) -> GpuProvisionResult:
    if not settings.openrouter_api_key:
        return GpuProvisionResult(
            success=False,
            message=(
                "GPU path unavailable and OpenRouter fallback is not configured. "
                "Set OPENROUTER_API_KEY in gpu-skill-builder/.env."
            ),
            fallback_activated=False,
            fallback_provider=Provider.OPENROUTER,
            fallback_reason=reason,
            primary_provider_error=primary_provider_error,
        )
    return GpuProvisionResult(
        success=True,
        instance=_openrouter_instance(instance_name),
        message=f"GPU path unavailable; switched to OpenRouter fallback. Reason: {reason}",
        fallback_activated=True,
        fallback_provider=Provider.OPENROUTER,
        fallback_reason=reason,
        primary_provider_error=primary_provider_error,
    )


# ── Runtime continuity helper ──────────────────────────────────────────────────

async def ensure_active_endpoint(result: GpuProvisionResult) -> GpuProvisionResult:
    """
    Verify active endpoint health and switch to OpenRouter fallback if needed.
    Use this in long-running sessions where TTL/provider failures can happen after
    provisioning has already succeeded.
    """
    if not result.success or not result.instance:
        return result
    if result.instance.provider == Provider.OPENROUTER:
        return result

    inst = result.instance
    provider_inst = PROVIDER_MAP[inst.provider]()
    try:
        current = await provider_inst.get_instance(inst.id)
    except Exception as exc:
        return _fallback_result(
            instance_name=inst.name,
            reason=f"{inst.provider.value} instance lookup failed ({exc})",
            primary_provider_error=str(exc),
        )

    if current.status not in ACTIVE_STATUSES:
        return _fallback_result(
            instance_name=inst.name,
            reason=f"{inst.provider.value} status is '{current.status}'",
            primary_provider_error=f"status={current.status}",
        )

    if current.endpoint_url:
        probe_url = f"{current.endpoint_url.rstrip('/')}/health"
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                resp = await client.get(probe_url)
            if resp.status_code >= 400:
                return _fallback_result(
                    instance_name=inst.name,
                    reason=f"{inst.provider.value} endpoint health check failed ({resp.status_code})",
                    primary_provider_error=f"http_status={resp.status_code}",
                )
        except Exception as exc:
            return _fallback_result(
                instance_name=inst.name,
                reason=f"{inst.provider.value} endpoint health check error ({exc})",
                primary_provider_error=str(exc),
            )

    return GpuProvisionResult(
        success=True,
        instance=current,
        message=result.message or "Instance is healthy.",
        fallback_activated=result.fallback_activated,
        fallback_provider=result.fallback_provider,
        fallback_reason=result.fallback_reason,
        primary_provider_error=result.primary_provider_error,
    )


# ── Main skill entry point ─────────────────────────────────────────────────────

async def run_skill(
    instance_name: str = "gpu-skill-instance",
    region: str = "us-east-1",
    max_deployment_hours: int | None = None,
    # Agent-mode params — supply all three to bypass interactive prompts
    provider: str | None = None,
    hardware_slug: str | None = None,
    model_repo_id: str | None = None,
) -> GpuProvisionResult:
    """
    Provision a GPU instance and load a model.

    Agent mode:   pass provider + hardware_slug + model_repo_id — no prompts.
    Interactive:  omit those three — presents selection menus and confirmation.
    """
    from scheduler import schedule_ttl, schedule_uptime_report, schedule_stuck_watchdog

    max_hours = max_deployment_hours or settings.max_deployment_hours
    agent_mode = all(x is not None for x in (provider, hardware_slug, model_repo_id))

    if agent_mode:
        try:
            provider_key = Provider(provider)
            if provider_key == Provider.OPENROUTER:
                return _fallback_result(instance_name, "OpenRouter selected explicitly by caller.")
            hardware = await _resolve_hardware(provider_key, hardware_slug)
            model = _resolve_model(hardware, model_repo_id)
        except (ValueError, KeyError) as exc:
            return GpuProvisionResult(success=False, message=str(exc))
    else:
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

    # ── Guardrail 1: pre-flight cost estimate ─────────────────────────────────
    estimated_cost = max_hours * hardware.price_per_hour
    if estimated_cost > settings.max_spend_per_instance_usd:
        return GpuProvisionResult(
            success=False,
            message=(
                f"Pre-flight cost check failed: estimated ${estimated_cost:.2f} "
                f"({max_hours}h × ${hardware.price_per_hour:.2f}/hr) exceeds limit "
                f"${settings.max_spend_per_instance_usd:.2f}. "
                f"Reduce max_deployment_hours or choose cheaper hardware."
            ),
        )

    # ── Guardrail 2 & 3: idempotency + concurrency cap ────────────────────────
    provider_inst = PROVIDER_MAP[provider_key]()
    try:
        existing = await provider_inst.list_instances()

        # Idempotency: return the instance if it already exists and is active
        for inst in existing:
            if inst.name == instance_name and inst.status in ACTIVE_STATUSES:
                print(f"[Guard] '{instance_name}' already exists (status={inst.status}) — returning it.")
                return GpuProvisionResult(
                    success=True,
                    instance=inst,
                    message=f"Existing instance returned (status={inst.status}).",
                )

        # Concurrency cap: reject if too many instances already live
        active_count = sum(1 for i in existing if i.status in ACTIVE_STATUSES)
        if active_count >= settings.max_concurrent_instances:
            names = [i.name for i in existing if i.status in ACTIVE_STATUSES]
            return GpuProvisionResult(
                success=False,
                message=(
                    f"Concurrency cap reached: {active_count}/{settings.max_concurrent_instances} "
                    f"instances active {names}. Destroy one before creating another."
                ),
            )
    except Exception as exc:
        # Non-fatal: log and continue rather than blocking on a list failure
        print(f"[Guard] Could not check existing instances: {exc}")

    # ── Provision ─────────────────────────────────────────────────────────────
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
        instance = await provider_inst.create_instance(request)
    except Exception as exc:
        return _fallback_result(
            instance_name=instance_name,
            reason=f"{provider_key.value} provisioning failed ({exc})",
            primary_provider_error=str(exc),
        )

    # Programmatic: schedule TTL + uptime + watchdog — never delegated to the LLM
    schedule_ttl(instance, max_hours)
    schedule_uptime_report(instance, settings.uptime_report_interval_minutes)
    schedule_stuck_watchdog(
        provider_key,
        timeout_minutes=settings.stuck_pending_minutes,
        check_interval_minutes=settings.watchdog_check_interval_minutes,
    )

    print(f"\nInstance '{instance.name}' created  [status: {instance.status}]")
    if instance.endpoint_url:
        print(f"Endpoint URL : {instance.endpoint_url}")

    result = GpuProvisionResult(success=True, instance=instance, message="Instance created successfully.")
    return await ensure_active_endpoint(result)
