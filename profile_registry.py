from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Literal, TypeVar

from pydantic import BaseModel, Field, field_validator

from models import InstanceInfo, Provider

PROFILES_ROOT = Path(__file__).resolve().parent / "profiles"
DEFAULT_HARNESS_PROFILE_ID = "openai-compatible-generic"


def _validate_profile_id(value: str) -> str:
    if not re.match(r"^[a-z0-9][a-z0-9._-]*$", value):
        raise ValueError(
            "profile id must start with lowercase alphanumeric and contain only "
            "lowercase letters, digits, '.', '_' and '-'"
        )
    return value


def _slugify(value: str) -> str:
    lowered = value.strip().lower()
    lowered = re.sub(r"[^a-z0-9._-]+", "-", lowered)
    lowered = re.sub(r"-{2,}", "-", lowered)
    return lowered.strip("-") or "profile"


def _default_alias_for_model(model_repo_id: str) -> str:
    return _slugify(model_repo_id.split("/")[-1])


def _deployment_variant_penalty(profile_id: str) -> int:
    lowered = profile_id.lower()
    return 1 if any(token in lowered for token in ("harness-eval", "benchmark", "smoke")) else 0


def _infer_gpu_count(hardware_slug: str) -> int:
    match = re.search(r"x(\d+)(?:-|$)", hardware_slug.lower())
    if match:
        return max(1, int(match.group(1)))
    return 1


class ModelLaunchHints(BaseModel):
    prefers_prefix_caching: bool | None = None
    prefers_chunked_prefill: bool | None = None
    prefers_expert_parallel: bool = False
    prefers_eplb: bool = False
    is_moe: bool = False
    notes: str = ""


class ModelProfile(BaseModel):
    kind: Literal["model_profile"] = "model_profile"
    id: str
    provider_model_id: str
    runtime_family: str = "openai-compatible"
    default_alias: str = ""
    context_window_tokens: int | None = Field(default=None, ge=1)
    throughput_hint: str = ""
    launch_hints: ModelLaunchHints = Field(default_factory=ModelLaunchHints)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return _validate_profile_id(value)

    @field_validator("provider_model_id")
    @classmethod
    def validate_provider_model_id(cls, value: str) -> str:
        if "/" not in value or value.count("/") != 1:
            raise ValueError("provider_model_id must be in owner/model format")
        return value

    @field_validator("default_alias")
    @classmethod
    def default_alias_if_missing(cls, value: str, info) -> str:
        if value.strip():
            return _slugify(value)
        provider_model_id = str(info.data.get("provider_model_id", "")).strip()
        return _default_alias_for_model(provider_model_id)


class DeploymentRuntimeProfile(BaseModel):
    port: int = Field(default=8000, ge=1, le=65535)
    max_model_len: int = Field(default=32768, ge=1)
    max_num_seqs: int = Field(default=4, ge=1)
    gpu_memory_utilization: float = Field(default=0.90, gt=0.0, le=0.99)
    max_num_batched_tokens: int = Field(default=8192, ge=1)
    tensor_parallel_size: int = Field(default=1, ge=1)
    pipeline_parallel_size: int = Field(default=1, ge=1)
    expert_parallel: bool = False
    enable_eplb: bool = False
    prefix_caching_policy: Literal["enabled", "disabled"] = "enabled"
    chunked_prefill_policy: Literal["enabled", "disabled"] = "enabled"
    kv_cache_dtype: str = "auto"
    extra_args: list[str] = Field(default_factory=list)

    @field_validator("extra_args")
    @classmethod
    def validate_extra_args(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for item in value:
            text = str(item).strip()
            if not text:
                continue
            cleaned.append(text)
        return cleaned


class DeploymentReadinessProfile(BaseModel):
    require_health_endpoint: bool = True
    require_models_endpoint: bool = True
    require_smoke_prompt: bool = True
    smoke_prompt: str = "Reply with OK"
    health_timeout_seconds: int = Field(default=1800, ge=1)


class DeploymentProfile(BaseModel):
    kind: Literal["deployment_profile"] = "deployment_profile"
    id: str
    model_profile_id: str = ""
    provider: Provider
    hardware_slug: str = "*"
    runtime_kind: str
    endpoint_class: str = "openai-compatible"
    managed_by_provider: bool = False
    served_model_name: str = ""
    description: str = ""
    runtime: DeploymentRuntimeProfile = Field(default_factory=DeploymentRuntimeProfile)
    readiness: DeploymentReadinessProfile = Field(default_factory=DeploymentReadinessProfile)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return _validate_profile_id(value)

    @field_validator("model_profile_id")
    @classmethod
    def validate_model_profile_id(cls, value: str) -> str:
        if not value:
            return value
        return _validate_profile_id(value)

    @field_validator("served_model_name")
    @classmethod
    def normalize_served_model_name(cls, value: str) -> str:
        return value.strip()


class HarnessEnvContract(BaseModel):
    base_url_key_name: str
    model_key_name: str
    api_key_key_name: str


class HarnessProfile(BaseModel):
    kind: Literal["harness_profile"] = "harness_profile"
    id: str
    harness_name: str
    protocol: str = "openai-compatible"
    base_url_mode: Literal["append-v1", "as-is"] = "append-v1"
    model_name_source: Literal["served_model_name", "provider_model_id", "default_alias"] = "served_model_name"
    expected_env: HarnessEnvContract

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return _validate_profile_id(value)


class GatewayProfile(BaseModel):
    kind: Literal["gateway_profile"] = "gateway_profile"
    id: str
    alias: str
    strategy: str = "direct"
    target_endpoint_class: str = "openai-compatible"
    notes: str = ""

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return _validate_profile_id(value)


class ProfileRegistry(BaseModel):
    model_profiles: dict[str, ModelProfile] = Field(default_factory=dict)
    deployment_profiles: dict[str, DeploymentProfile] = Field(default_factory=dict)
    harness_profiles: dict[str, HarnessProfile] = Field(default_factory=dict)
    gateway_profiles: dict[str, GatewayProfile] = Field(default_factory=dict)

    def validate_references(self) -> None:
        for deployment in self.deployment_profiles.values():
            if deployment.model_profile_id and deployment.model_profile_id not in self.model_profiles:
                raise ValueError(
                    f"deployment profile {deployment.id!r} references missing model profile "
                    f"{deployment.model_profile_id!r}"
                )

    def model_profile_for_repo(self, model_repo_id: str) -> ModelProfile | None:
        for profile in self.model_profiles.values():
            if profile.provider_model_id == model_repo_id:
                return profile
        return None

    def deployment_profile_for(
        self,
        *,
        provider: Provider,
        hardware_slug: str,
        model_profile_id: str,
    ) -> DeploymentProfile | None:
        candidates = [
            (provider, hardware_slug, model_profile_id),
            (provider, hardware_slug, ""),
            (provider, "*", model_profile_id),
            (provider, "*", ""),
        ]
        for candidate_provider, candidate_hardware, candidate_model_id in candidates:
            matches: list[DeploymentProfile] = []
            for profile in self.deployment_profiles.values():
                if profile.provider != candidate_provider:
                    continue
                if profile.hardware_slug != candidate_hardware:
                    continue
                if profile.model_profile_id != candidate_model_id:
                    continue
                matches.append(profile)
            if matches:
                return sorted(
                    matches,
                    key=lambda profile: (_deployment_variant_penalty(profile.id), len(profile.id), profile.id),
                )[0]
        return None

    def harness_profile_for(self, harness_profile_id: str) -> HarnessProfile:
        try:
            return self.harness_profiles[harness_profile_id]
        except KeyError as exc:
            raise KeyError(f"unknown harness profile {harness_profile_id!r}") from exc


class ResolvedRuntimeSelection(BaseModel):
    model_profile: ModelProfile
    deployment_profile: DeploymentProfile
    harness_profile: HarnessProfile
    gateway_profile: GatewayProfile | None = None


T = TypeVar("T", bound=BaseModel)


def _load_json_directory(directory: Path, model_type: type[T]) -> dict[str, T]:
    items: dict[str, T] = {}
    if not directory.exists():
        return items
    for path in sorted(directory.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        item = model_type.model_validate(payload)
        if item.id in items:
            raise ValueError(f"duplicate profile id {item.id!r} in {directory}")
        items[item.id] = item
    return items


def load_profile_registry(base_dir: Path | None = None) -> ProfileRegistry:
    root = base_dir or PROFILES_ROOT
    registry = ProfileRegistry(
        model_profiles=_load_json_directory(root / "models", ModelProfile),
        deployment_profiles=_load_json_directory(root / "deployments", DeploymentProfile),
        harness_profiles=_load_json_directory(root / "harnesses", HarnessProfile),
        gateway_profiles=_load_json_directory(root / "gateways", GatewayProfile),
    )
    registry.validate_references()
    return registry


@lru_cache(maxsize=1)
def get_profile_registry() -> ProfileRegistry:
    return load_profile_registry()


def clear_profile_registry_cache() -> None:
    get_profile_registry.cache_clear()


def _generated_model_profile(model_repo_id: str) -> ModelProfile:
    return ModelProfile(
        id=f"generated-{_slugify(model_repo_id.replace('/', '-'))}",
        provider_model_id=model_repo_id,
        runtime_family="openai-compatible",
        default_alias=_default_alias_for_model(model_repo_id),
        throughput_hint="generated fallback profile",
    )


def _default_runtime_for_generated_deployment(
    provider: Provider,
    hardware_slug: str,
    model_profile: ModelProfile,
) -> DeploymentRuntimeProfile:
    gpu_count = _infer_gpu_count(hardware_slug)
    prefix_caching = (
        "enabled" if model_profile.launch_hints.prefers_prefix_caching is not False else "disabled"
    )
    chunked_prefill = (
        "enabled" if model_profile.launch_hints.prefers_chunked_prefill is not False else "disabled"
    )
    expert_parallel = model_profile.launch_hints.prefers_expert_parallel or (
        model_profile.launch_hints.is_moe and gpu_count > 1
    )
    max_num_seqs = 4 if gpu_count == 1 else 8
    max_num_batched_tokens = 8192 if gpu_count == 1 else 16384
    gpu_memory_utilization = 0.90 if provider != Provider.DIGITALOCEAN or gpu_count == 1 else 0.80
    tensor_parallel_size = gpu_count if provider == Provider.DIGITALOCEAN else 1
    return DeploymentRuntimeProfile(
        port=8000,
        max_model_len=model_profile.context_window_tokens or 32768,
        max_num_seqs=max_num_seqs,
        gpu_memory_utilization=gpu_memory_utilization,
        max_num_batched_tokens=max_num_batched_tokens,
        tensor_parallel_size=tensor_parallel_size,
        pipeline_parallel_size=1,
        expert_parallel=expert_parallel,
        enable_eplb=model_profile.launch_hints.prefers_eplb,
        prefix_caching_policy=prefix_caching,
        chunked_prefill_policy=chunked_prefill,
    )


def _generated_deployment_profile(
    *,
    provider: Provider,
    hardware_slug: str,
    model_profile: ModelProfile,
) -> DeploymentProfile:
    if provider == Provider.DIGITALOCEAN:
        runtime_kind = "vllm"
        managed_by_provider = False
        served_model_name = model_profile.default_alias
    elif provider == Provider.MODAL:
        runtime_kind = "modal-vllm"
        managed_by_provider = True
        served_model_name = model_profile.provider_model_id
    elif provider == Provider.HUGGINGFACE:
        runtime_kind = "huggingface-endpoint"
        managed_by_provider = True
        served_model_name = model_profile.provider_model_id
    elif provider == Provider.OPENROUTER:
        runtime_kind = "openrouter-fallback"
        managed_by_provider = True
        served_model_name = model_profile.provider_model_id
    else:
        runtime_kind = "unknown"
        managed_by_provider = True
        served_model_name = model_profile.provider_model_id

    return DeploymentProfile(
        id=f"generated-{provider.value}-{_slugify(hardware_slug)}-{_slugify(model_profile.id)}",
        model_profile_id=model_profile.id,
        provider=provider,
        hardware_slug=hardware_slug,
        runtime_kind=runtime_kind,
        endpoint_class="openai-compatible",
        managed_by_provider=managed_by_provider,
        served_model_name=served_model_name,
        description="generated fallback deployment profile",
        runtime=_default_runtime_for_generated_deployment(provider, hardware_slug, model_profile),
    )


def resolve_runtime_selection(
    *,
    provider: Provider,
    hardware_slug: str,
    model_repo_id: str,
    model_profile_id: str = "",
    deployment_profile_id: str = "",
    harness_profile_id: str = "",
    registry: ProfileRegistry | None = None,
) -> ResolvedRuntimeSelection:
    registry = registry or get_profile_registry()
    if model_profile_id:
        model_profile = registry.model_profiles.get(model_profile_id)
        if model_profile is None:
            if not model_repo_id:
                raise KeyError(f"unknown model profile {model_profile_id!r}")
            generated_model_profile = _generated_model_profile(model_repo_id)
            if generated_model_profile.id != model_profile_id:
                raise KeyError(f"unknown model profile {model_profile_id!r}")
            model_profile = generated_model_profile
    else:
        model_profile = registry.model_profile_for_repo(model_repo_id) or _generated_model_profile(model_repo_id)

    if deployment_profile_id:
        deployment_profile = registry.deployment_profiles.get(deployment_profile_id)
        if deployment_profile is None:
            generated_deployment_profile = _generated_deployment_profile(
                provider=provider,
                hardware_slug=hardware_slug,
                model_profile=model_profile,
            )
            if generated_deployment_profile.id != deployment_profile_id:
                raise KeyError(f"unknown deployment profile {deployment_profile_id!r}")
            deployment_profile = generated_deployment_profile
    else:
        deployment_profile = registry.deployment_profile_for(
            provider=provider,
            hardware_slug=hardware_slug,
            model_profile_id=model_profile.id,
        ) or _generated_deployment_profile(
            provider=provider,
            hardware_slug=hardware_slug,
            model_profile=model_profile,
        )

    resolved_harness_id = harness_profile_id or DEFAULT_HARNESS_PROFILE_ID
    harness_profile = registry.harness_profile_for(resolved_harness_id)

    return ResolvedRuntimeSelection(
        model_profile=model_profile,
        deployment_profile=deployment_profile,
        harness_profile=harness_profile,
    )


def _resolved_served_model_name(instance: InstanceInfo, selection: ResolvedRuntimeSelection) -> str:
    if instance.served_model_name.strip():
        return instance.served_model_name.strip()
    if selection.deployment_profile.served_model_name.strip():
        return selection.deployment_profile.served_model_name.strip()
    return selection.model_profile.provider_model_id


def apply_runtime_selection(
    instance: InstanceInfo,
    selection: ResolvedRuntimeSelection,
) -> InstanceInfo:
    payload = instance.model_dump()
    payload.update(
        {
            "runtime_kind": selection.deployment_profile.runtime_kind,
            "endpoint_class": selection.deployment_profile.endpoint_class,
            "managed_by_provider": selection.deployment_profile.managed_by_provider,
            "deployment_profile_id": selection.deployment_profile.id,
            "model_profile_id": selection.model_profile.id,
            "harness_profile_id": selection.harness_profile.id,
            "served_model_name": _resolved_served_model_name(instance, selection),
        }
    )
    return InstanceInfo.model_validate(payload)


def resolve_runtime_selection_for_instance(
    instance: InstanceInfo,
    *,
    harness_profile_id: str = "",
    registry: ProfileRegistry | None = None,
) -> ResolvedRuntimeSelection:
    return resolve_runtime_selection(
        provider=instance.provider,
        hardware_slug=instance.hardware_slug,
        model_repo_id=instance.model_repo_id,
        model_profile_id=instance.model_profile_id,
        deployment_profile_id=instance.deployment_profile_id,
        harness_profile_id=harness_profile_id or instance.harness_profile_id,
        registry=registry,
    )


def hydrate_instance_runtime_metadata(
    instance: InstanceInfo,
    *,
    harness_profile_id: str = "",
    registry: ProfileRegistry | None = None,
) -> InstanceInfo:
    if not instance.model_repo_id:
        return instance
    selection = resolve_runtime_selection_for_instance(
        instance,
        harness_profile_id=harness_profile_id,
        registry=registry,
    )
    return apply_runtime_selection(instance, selection)
