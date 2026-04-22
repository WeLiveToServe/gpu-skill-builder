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

import asyncio
import concurrent.futures
import logging

from catalog import get_compatible_models
from config import settings
from endpoint_probe import ProbeClassification, probe_openai_compatible_endpoint
from handoff import build_harness_handoff_manifest
from models import GpuProvisionRequest, GpuProvisionResult, HardwareTier, InstanceInfo, ModelRecommendation, Provider
from profile_registry import (
    ResolvedRuntimeSelection,
    apply_runtime_selection,
    hydrate_instance_runtime_metadata,
    resolve_runtime_selection,
)
from providers import PROVIDER_MAP
from providers.base import classify_http_error

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = {"pending", "initializing", "running", "deployed"}
READINESS_PROVISIONED = "provisioned-unverified"
READINESS_VERIFIED = "verified-ready"
READINESS_FALLBACK = "fallback-active"


# ── Interactive prompts ────────────────────────────────────────────────────────

def _pick_provider() -> Provider:
    options = [p for p in PROVIDER_MAP.keys() if p not in (Provider.OPENROUTER, Provider.AMD)]
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


def _profile_backed_model_recommendation(
    *,
    provider_key: Provider,
    hardware: HardwareTier,
    model_repo_id: str,
    model_profile_id: str = "",
    deployment_profile_id: str = "",
    harness_profile_id: str = "",
) -> tuple[ModelRecommendation, ResolvedRuntimeSelection]:
    selection = resolve_runtime_selection(
        provider=provider_key,
        hardware_slug=hardware.slug,
        model_repo_id=model_repo_id,
        model_profile_id=model_profile_id,
        deployment_profile_id=deployment_profile_id,
        harness_profile_id=harness_profile_id,
    )
    return (
        ModelRecommendation(
            repo_id=selection.model_profile.provider_model_id,
            display_name=selection.model_profile.default_alias,
            size_params="profile",
            vram_required_gb=hardware.vram_gb,
            notes="resolved from committed/generative profile registry",
        ),
        selection,
    )


def _result_from_instance(
    *,
    instance: InstanceInfo,
    message: str,
    readiness_state: str,
    fallback_activated: bool = False,
    fallback_provider: Provider | None = None,
    fallback_reason: str = "",
    primary_provider_error: str | None = None,
) -> GpuProvisionResult:
    hydrated = hydrate_instance_runtime_metadata(instance, harness_profile_id=instance.harness_profile_id)
    handoff = None
    if hydrated.endpoint_url:
        handoff = build_harness_handoff_manifest(
            hydrated,
            readiness_state=readiness_state,
        )
    return GpuProvisionResult(
        success=True,
        instance=hydrated,
        message=message,
        readiness_state=readiness_state,
        harness_handoff=handoff,
        fallback_activated=fallback_activated,
        fallback_provider=fallback_provider,
        fallback_reason=fallback_reason,
        primary_provider_error=primary_provider_error,
    )


def _openrouter_instance(instance_name: str) -> InstanceInfo:
    return hydrate_instance_runtime_metadata(
        InstanceInfo(
            id=f"{instance_name}-openrouter-fallback",
            name=instance_name,
            provider=Provider.OPENROUTER,
            hardware_slug="openrouter-default",
            model_repo_id=settings.openrouter_model,
            served_model_name=settings.openrouter_model,
            status="running",
            endpoint_url=settings.openrouter_base_url.rstrip("/"),
            region="global",
        )
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
            readiness_state=READINESS_FALLBACK,
            fallback_activated=False,
            fallback_provider=Provider.OPENROUTER,
            fallback_reason=reason,
            primary_provider_error=primary_provider_error,
        )
    return _result_from_instance(
        instance=_openrouter_instance(instance_name),
        message=f"GPU path unavailable; switched to OpenRouter fallback. Reason: {reason}",
        readiness_state=READINESS_FALLBACK,
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
        return _result_from_instance(
            instance=result.instance,
            message=result.message or "OpenRouter fallback is active.",
            readiness_state=READINESS_FALLBACK,
            fallback_activated=result.fallback_activated,
            fallback_provider=result.fallback_provider,
            fallback_reason=result.fallback_reason,
            primary_provider_error=result.primary_provider_error,
        )

    inst = result.instance
    provider_inst = PROVIDER_MAP[inst.provider]()
    try:
        current = await provider_inst.get_instance(inst.id)
    except Exception as exc:
        detail = classify_http_error(exc)
        return _fallback_result(
            instance_name=inst.name,
            reason=f"{inst.provider.value} instance lookup failed: {detail}",
            primary_provider_error=detail,
        )

    if current.status not in ACTIVE_STATUSES and not current.endpoint_url:
        return _fallback_result(
            instance_name=inst.name,
            reason=f"{inst.provider.value} status is '{current.status}'",
            primary_provider_error=f"status={current.status}",
        )

    current = hydrate_instance_runtime_metadata(current, harness_profile_id=inst.harness_profile_id)

    if current.endpoint_url:
        probe = await probe_openai_compatible_endpoint(
            current,
            expected_model_id=current.served_model_name or current.model_repo_id or None,
        )
        if probe.classification != ProbeClassification.READY:
            return _fallback_result(
                instance_name=inst.name,
                reason=f"{inst.provider.value} endpoint probe returned {probe.classification.value}: {probe.detail}",
                primary_provider_error=f"{probe.classification.value}: {probe.detail}",
            )

    return _result_from_instance(
        instance=current,
        message=result.message or "Instance is healthy.",
        readiness_state=READINESS_VERIFIED,
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
    deployment_profile_id: str | None = None,
    model_profile_id: str | None = None,
    harness_profile_id: str | None = None,
) -> GpuProvisionResult:
    """
    Provision a GPU instance and load a model.

    Agent mode:   pass provider + hardware_slug + model_repo_id — no prompts.
    Interactive:  omit those three — presents selection menus and confirmation.
    """
    from scheduler import (
        schedule_readiness_watch,
        schedule_fleet_monitoring,
        schedule_ttl,
        schedule_uptime_report,
        schedule_stuck_watchdog,
    )
    from monitor import monitor_instance_once

    max_hours = max_deployment_hours or settings.max_deployment_hours
    agent_mode = all(x is not None for x in (provider, hardware_slug, model_repo_id))

    if agent_mode:
        try:
            provider_key = Provider(provider)
            if provider_key == Provider.AMD:
                return GpuProvisionResult(
                    success=False,
                    message=(
                        "AMD / MI300X support is blocked pending DigitalOcean GPU account entitlement. "
                        "No provider integration exists yet. "
                        "Use 'modal' or 'huggingface' instead. See handoff-plan.md for status."
                    ),
                )
            if provider_key == Provider.OPENROUTER:
                return _fallback_result(instance_name, "OpenRouter selected explicitly by caller.")
            hardware = await _resolve_hardware(provider_key, hardware_slug)
            selection = None
            try:
                model = _resolve_model(hardware, model_repo_id)
            except ValueError:
                model, selection = _profile_backed_model_recommendation(
                    provider_key=provider_key,
                    hardware=hardware,
                    model_repo_id=model_repo_id,
                    model_profile_id=model_profile_id or "",
                    deployment_profile_id=deployment_profile_id or "",
                    harness_profile_id=harness_profile_id or "",
                )
        except (ValueError, KeyError) as exc:
            return GpuProvisionResult(success=False, message=str(exc))
    else:
        provider_key = _pick_provider()
        hardware = await _pick_hardware(provider_key)
        model = _pick_model(hardware)
        selection = None

        print("\n── Summary ──────────────────────────────────")
        print(f"  Provider  : {provider_key.value}")
        print(f"  Hardware  : {hardware.display_name}")
        print(f"  Model     : {model.display_name}  ({model.repo_id})")
        print(f"  Region    : {region}")
        print(f"  TTL       : {max_hours}h  (auto-destroy enforced)")
        print("─────────────────────────────────────────────")

        if input("\nProceed? [y/N]: ").strip().lower() != "y":
            return GpuProvisionResult(success=False, message="Cancelled by user.")

    if not agent_mode:
        selection = resolve_runtime_selection(
            provider=provider_key,
            hardware_slug=hardware.slug,
            model_repo_id=model.repo_id,
            model_profile_id=model_profile_id or "",
            deployment_profile_id=deployment_profile_id or "",
            harness_profile_id=harness_profile_id or "",
        )
    elif selection is None:
        selection = resolve_runtime_selection(
            provider=provider_key,
            hardware_slug=hardware.slug,
            model_repo_id=model.repo_id,
            model_profile_id=model_profile_id or "",
            deployment_profile_id=deployment_profile_id or "",
            harness_profile_id=harness_profile_id or "",
        )

    # ── Guardrail 1: pre-flight cost estimate ──────────────────────────────────
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
                logger.info("[Guard] '%s' already exists (status=%s) — returning it.", instance_name, inst.status)
                inst = apply_runtime_selection(inst, selection)
                return _result_from_instance(
                    instance=inst,
                    message=f"Existing instance returned (status={inst.status}).",
                    readiness_state=READINESS_PROVISIONED,
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
        logger.warning("[Guard] Could not check existing instances: %s", exc)

    # ── Provision ─────────────────────────────────────────────────────────────
    request = GpuProvisionRequest(
        provider=provider_key,
        hardware_slug=hardware.slug,
        model_repo_id=model.repo_id,
        instance_name=instance_name,
        region=region,
        max_deployment_hours=max_hours,
        deployment_profile_id=selection.deployment_profile.id,
        model_profile_id=selection.model_profile.id,
        harness_profile_id=selection.harness_profile.id,
    )

    logger.info("Provisioning instance '%s' on %s...", instance_name, provider_key.value)
    try:
        instance = await provider_inst.create_instance(request)
    except Exception as exc:
        error_detail = classify_http_error(exc)
        return _fallback_result(
            instance_name=instance_name,
            reason=f"{provider_key.value} provisioning failed: {error_detail}",
            primary_provider_error=error_detail,
        )
    try:
        instance = InstanceInfo.model_validate(instance)
    except Exception as exc:
        return GpuProvisionResult(
            success=False,
            message=(
                f"{provider_key.value} provider returned invalid instance payload: {exc}"
            ),
        )
    instance = apply_runtime_selection(instance, selection)

    # Programmatic: schedule TTL + uptime + watchdog — never delegated to the LLM
    schedule_ttl(instance, max_hours)
    schedule_uptime_report(instance, settings.uptime_report_interval_minutes)
    schedule_stuck_watchdog(
        provider_key,
        timeout_minutes=settings.stuck_pending_minutes,
        check_interval_minutes=settings.watchdog_check_interval_minutes,
    )
    if settings.monitor_enabled:
        continue_watch = await monitor_instance_once(
            provider_key,
            instance.id,
            runtime_alert_minutes=settings.monitor_runtime_alert_minutes,
            auto_stop_minutes=settings.monitor_auto_stop_minutes,
            readiness_timeout_minutes=settings.monitor_readiness_timeout_minutes,
            stale_after_minutes=settings.monitor_stale_after_minutes,
            unhealthy_auto_stop_minutes=settings.monitor_unhealthy_auto_stop_minutes,
        )
        if continue_watch:
            schedule_readiness_watch(
                instance,
                poll_seconds=settings.monitor_readiness_poll_seconds,
                runtime_alert_minutes=settings.monitor_runtime_alert_minutes,
                auto_stop_minutes=settings.monitor_auto_stop_minutes,
                readiness_timeout_minutes=settings.monitor_readiness_timeout_minutes,
                stale_after_minutes=settings.monitor_stale_after_minutes,
                unhealthy_auto_stop_minutes=settings.monitor_unhealthy_auto_stop_minutes,
            )
        schedule_fleet_monitoring(
            interval_minutes=settings.monitor_interval_minutes,
            runtime_alert_minutes=settings.monitor_runtime_alert_minutes,
            auto_stop_minutes=settings.monitor_auto_stop_minutes,
            readiness_timeout_minutes=settings.monitor_readiness_timeout_minutes,
            stale_after_minutes=settings.monitor_stale_after_minutes,
            unhealthy_auto_stop_minutes=settings.monitor_unhealthy_auto_stop_minutes,
        )

    logger.info("Instance '%s' created [status: %s]", instance.name, instance.status)
    if instance.endpoint_url:
        logger.info("Endpoint URL: %s", instance.endpoint_url)

    message = "Instance created successfully."
    if settings.monitor_enabled:
        message = "Instance created; readiness monitoring is active."
    return _result_from_instance(
        instance=instance,
        message=message,
        readiness_state=READINESS_PROVISIONED,
    )


def run_skill_sync(**kwargs) -> GpuProvisionResult:
    """
    Sync wrapper for run_skill(). Safe to call from both sync and async contexts.
    If an event loop is already running (FastAPI, Jupyter), spawns a thread to avoid
    'asyncio.run() cannot be called from a running event loop'.
    """
    try:
        asyncio.get_running_loop()
        # Already inside an event loop — run in a thread with its own loop
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, run_skill(**kwargs)).result()
    except RuntimeError:
        return asyncio.run(run_skill(**kwargs))


def ensure_active_endpoint_sync(result: GpuProvisionResult) -> GpuProvisionResult:
    """
    Sync wrapper for ensure_active_endpoint(). Mirrors run_skill_sync behavior.
    """
    try:
        asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, ensure_active_endpoint(result)).result()
    except RuntimeError:
        return asyncio.run(ensure_active_endpoint(result))
