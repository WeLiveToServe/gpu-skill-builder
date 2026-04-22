from __future__ import annotations

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings
from do_bootstrap import (
    DO_API,
    SSH_KEY_PATH,
    DropletInfo,
    _load_state,
    _save_state,
    _headers,
    create_droplet,
    resolve_token,
)
from models import GpuProvisionRequest, HardwareTier, InstanceInfo, Provider
from profile_registry import (
    apply_runtime_selection,
    hydrate_instance_runtime_metadata,
    resolve_runtime_selection,
)
from providers.base import GpuProvider
from remote_vllm import DEFAULT_VLLM_PORT, deploy_vllm_remote


def _normalize_status(status: str) -> str:
    return {
        "active": "running",
        "new": "pending",
    }.get(status, status)


def _build_endpoint_url(ip: str, port: int = DEFAULT_VLLM_PORT) -> str:
    return f"http://{ip}:{port}" if ip else ""


def _load_model_map() -> dict[str, str]:
    raw = _load_state().get("droplet_models", {})
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in raw.items()}


def _load_runtime_meta_map() -> dict[str, dict[str, object]]:
    raw = _load_state().get("droplet_runtime_meta", {})
    if not isinstance(raw, dict):
        return {}
    result: dict[str, dict[str, object]] = {}
    for key, value in raw.items():
        if isinstance(value, dict):
            result[str(key)] = value
    return result


def _runtime_meta_from_instance(instance: InstanceInfo) -> dict[str, object]:
    return {
        "model_repo_id": instance.model_repo_id,
        "served_model_name": instance.served_model_name,
        "runtime_kind": instance.runtime_kind,
        "endpoint_class": instance.endpoint_class,
        "managed_by_provider": instance.managed_by_provider,
        "deployment_profile_id": instance.deployment_profile_id,
        "model_profile_id": instance.model_profile_id,
        "harness_profile_id": instance.harness_profile_id,
    }


def _save_runtime_metadata(instance: InstanceInfo) -> None:
    state = _load_state()
    droplet_models = state.get("droplet_models", {})
    if not isinstance(droplet_models, dict):
        droplet_models = {}
    droplet_models[str(instance.id)] = instance.model_repo_id
    state["droplet_models"] = droplet_models

    runtime_meta = state.get("droplet_runtime_meta", {})
    if not isinstance(runtime_meta, dict):
        runtime_meta = {}
    runtime_meta[str(instance.id)] = _runtime_meta_from_instance(instance)
    state["droplet_runtime_meta"] = runtime_meta
    _save_state(state)


def _clear_runtime_metadata(droplet_id: str) -> None:
    state = _load_state()
    droplet_models = state.get("droplet_models", {})
    if isinstance(droplet_models, dict) and droplet_id in droplet_models:
        del droplet_models[droplet_id]
        state["droplet_models"] = droplet_models

    runtime_meta = state.get("droplet_runtime_meta", {})
    if isinstance(runtime_meta, dict) and droplet_id in runtime_meta:
        del runtime_meta[droplet_id]
        state["droplet_runtime_meta"] = runtime_meta
    _save_state(state)


def _lookup_model_repo_id(droplet_id: str) -> str:
    runtime_meta = _load_runtime_meta_map().get(droplet_id, {})
    model_repo_id = str(runtime_meta.get("model_repo_id", "")).strip()
    if model_repo_id:
        return model_repo_id
    return _load_model_map().get(droplet_id, "")


def _lookup_runtime_meta(droplet_id: str) -> dict[str, object]:
    return _load_runtime_meta_map().get(droplet_id, {})


def _apply_saved_runtime_metadata(instance: InstanceInfo, saved_meta: dict[str, object]) -> InstanceInfo:
    if not saved_meta:
        return hydrate_instance_runtime_metadata(instance)
    payload = instance.model_dump()
    for key in (
        "model_repo_id",
        "served_model_name",
        "runtime_kind",
        "endpoint_class",
        "managed_by_provider",
        "deployment_profile_id",
        "model_profile_id",
        "harness_profile_id",
    ):
        if key in saved_meta:
            payload[key] = saved_meta[key]
    hydrated = InstanceInfo.model_validate(payload)
    if not hydrated.runtime_kind:
        return hydrate_instance_runtime_metadata(hydrated)
    return hydrated


def _to_instance_info(d: DropletInfo, model_repo_id: str = "", endpoint_url: str = "") -> InstanceInfo:
    return InstanceInfo(
        id=str(d.id),
        name=d.name,
        provider=Provider.DIGITALOCEAN,
        hardware_slug=d.size,
        model_repo_id=model_repo_id,
        status=_normalize_status(d.status),
        endpoint_url=endpoint_url or _build_endpoint_url(d.ip),
        region=d.region,
    )


class DigitalOceanProvider(GpuProvider):
    def __init__(self) -> None:
        self.token = resolve_token()

    async def list_hardware(self) -> list[HardwareTier]:
        async with httpx.AsyncClient(headers=_headers(self.token), timeout=15) as client:
            resp = await client.get(f"{DO_API}/sizes?per_page=200")
            resp.raise_for_status()

        _VRAM_MAP = {
            "gpu-h100x1-80gb": 80,
            "gpu-h200x1-141gb": 141,
            "gpu-h100x8-640gb": 640,
            "gpu-h200x8-1128gb": 1128,
            "gpu-l40sx1-48gb": 48,
            "gpu-a100x1-80gb": 80,
            "gpu-mi300x1-192gb": 192,
        }
        tiers: list[HardwareTier] = []
        for size in resp.json().get("sizes", []):
            if "gpu" not in size["slug"]:
                continue
            regions = size.get("regions") or []
            slug = size["slug"]
            tiers.append(
                HardwareTier(
                    slug=slug,
                    display_name=size.get("description", slug),
                    vram_gb=_VRAM_MAP.get(slug, 0),
                    price_per_hour=size.get("price_hourly", 0.0),
                    provider=Provider.DIGITALOCEAN,
                    region=regions[0] if regions else "",
                )
            )
        return tiers

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=5, max=30))
    async def create_instance(self, request: GpuProvisionRequest) -> InstanceInfo:
        selection = resolve_runtime_selection(
            provider=request.provider,
            hardware_slug=request.hardware_slug,
            model_repo_id=request.model_repo_id,
            model_profile_id=request.model_profile_id,
            deployment_profile_id=request.deployment_profile_id,
            harness_profile_id=request.harness_profile_id,
        )
        droplet = await create_droplet(
            size=request.hardware_slug,
            name=request.instance_name,
        )
        endpoint_url = await deploy_vllm_remote(
            ip=droplet.ip,
            model_id=request.model_repo_id,
            ssh_key_path=SSH_KEY_PATH,
            hf_token=settings.hf_token or None,
            deployment_profile=selection.deployment_profile,
            model_profile=selection.model_profile,
        )
        instance = _to_instance_info(droplet, request.model_repo_id, endpoint_url=endpoint_url)
        instance = apply_runtime_selection(instance, selection)
        _save_runtime_metadata(instance)
        return instance

    async def get_instance(self, instance_id: str) -> InstanceInfo:
        async with httpx.AsyncClient(headers=_headers(self.token), timeout=15) as client:
            resp = await client.get(f"{DO_API}/droplets/{instance_id}")
            resp.raise_for_status()
        d = resp.json()["droplet"]
        nets = d.get("networks", {}).get("v4", [])
        ip = next((n["ip_address"] for n in nets if n["type"] == "public"), "")
        instance = InstanceInfo(
            id=str(d["id"]),
            name=d["name"],
            provider=Provider.DIGITALOCEAN,
            hardware_slug=d["size_slug"],
            model_repo_id=_lookup_model_repo_id(str(d["id"])),
            status=_normalize_status(d["status"]),
            endpoint_url=_build_endpoint_url(ip),
            region=d["region"]["slug"],
        )
        return _apply_saved_runtime_metadata(instance, _lookup_runtime_meta(str(d["id"])))

    async def destroy_instance(self, instance_id: str) -> bool:
        async with httpx.AsyncClient(headers=_headers(self.token), timeout=15) as client:
            resp = await client.delete(f"{DO_API}/droplets/{instance_id}")
        if resp.status_code == 204:
            _clear_runtime_metadata(instance_id)
            return True
        return False

    async def list_instances(self) -> list[InstanceInfo]:
        async with httpx.AsyncClient(headers=_headers(self.token), timeout=15) as client:
            resp = await client.get(f"{DO_API}/droplets?tag_name=agent-harness&per_page=200")
            resp.raise_for_status()
        result = []
        for d in resp.json().get("droplets", []):
            nets = d.get("networks", {}).get("v4", [])
            ip = next((n["ip_address"] for n in nets if n["type"] == "public"), "")
            instance = InstanceInfo(
                id=str(d["id"]),
                name=d["name"],
                provider=Provider.DIGITALOCEAN,
                hardware_slug=d["size_slug"],
                model_repo_id=_lookup_model_repo_id(str(d["id"])),
                status=_normalize_status(d["status"]),
                endpoint_url=_build_endpoint_url(ip),
                region=d["region"]["slug"],
            )
            result.append(_apply_saved_runtime_metadata(instance, _lookup_runtime_meta(str(d["id"]))))
        return result
