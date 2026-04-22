from __future__ import annotations

from models import HarnessHandoffEnv, HarnessHandoffManifest, InstanceInfo
from profile_registry import ResolvedRuntimeSelection, resolve_runtime_selection_for_instance


def normalize_harness_base_url(url: str, mode: str) -> str:
    base = url.rstrip("/")
    if mode == "as-is":
        return base
    if base.endswith("/v1"):
        return base
    return f"{base}/v1"


def _select_harness_model_name(
    instance: InstanceInfo,
    selection: ResolvedRuntimeSelection,
) -> str:
    source = selection.harness_profile.model_name_source
    if source == "provider_model_id":
        return selection.model_profile.provider_model_id
    if source == "default_alias":
        return selection.model_profile.default_alias
    return instance.served_model_name or selection.deployment_profile.served_model_name or selection.model_profile.provider_model_id


def build_harness_handoff_manifest(
    instance: InstanceInfo,
    *,
    readiness_state: str,
    selection: ResolvedRuntimeSelection | None = None,
) -> HarnessHandoffManifest:
    selection = selection or resolve_runtime_selection_for_instance(instance)
    base_url = normalize_harness_base_url(
        instance.endpoint_url,
        selection.harness_profile.base_url_mode,
    )
    model_name = _select_harness_model_name(instance, selection)
    return HarnessHandoffManifest(
        harness_profile_id=selection.harness_profile.id,
        harness_name=selection.harness_profile.harness_name,
        protocol=selection.harness_profile.protocol,
        provider=instance.provider.value,
        hardware_slug=instance.hardware_slug,
        instance_id=instance.id,
        instance_name=instance.name,
        endpoint_url=instance.endpoint_url.rstrip("/"),
        base_url=base_url,
        runtime_kind=instance.runtime_kind,
        endpoint_class=instance.endpoint_class,
        managed_by_provider=instance.managed_by_provider,
        model_repo_id=instance.model_repo_id,
        served_model_name=instance.served_model_name,
        model_name=model_name,
        deployment_profile_id=instance.deployment_profile_id,
        model_profile_id=instance.model_profile_id,
        readiness_state=readiness_state,
        expected_env=HarnessHandoffEnv(
            base_url_key_name=selection.harness_profile.expected_env.base_url_key_name,
            model_key_name=selection.harness_profile.expected_env.model_key_name,
            api_key_key_name=selection.harness_profile.expected_env.api_key_key_name,
        ),
    )
