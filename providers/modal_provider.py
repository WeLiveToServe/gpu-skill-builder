from __future__ import annotations

from modal_bootstrap import (
    GPU_SLUG_MAP,
    ModalInstanceInfo,
    deploy_vllm_app,
    list_apps,
    normalize_gpu,
    stop_app,
)
from models import GpuProvisionRequest, HardwareTier, InstanceInfo, Provider
from providers.base import GpuProvider

# Deterministic hardware catalog — no LLM involvement
MODAL_HARDWARE: list[HardwareTier] = [
    HardwareTier(slug="T4",        display_name="NVIDIA T4 (16 GB)",        vram_gb=16,  price_per_hour=0.59,  provider=Provider.MODAL),
    HardwareTier(slug="L4",        display_name="NVIDIA L4 (24 GB)",         vram_gb=24,  price_per_hour=0.80,  provider=Provider.MODAL),
    HardwareTier(slug="A10",       display_name="NVIDIA A10 (24 GB)",        vram_gb=24,  price_per_hour=1.10,  provider=Provider.MODAL),
    HardwareTier(slug="L40S",      display_name="NVIDIA L40S (48 GB)",       vram_gb=48,  price_per_hour=1.95,  provider=Provider.MODAL),
    HardwareTier(slug="A100-40GB", display_name="NVIDIA A100 40 GB",         vram_gb=40,  price_per_hour=2.10,  provider=Provider.MODAL),
    HardwareTier(slug="A100-80GB", display_name="NVIDIA A100 80 GB",         vram_gb=80,  price_per_hour=2.50,  provider=Provider.MODAL),
    HardwareTier(slug="H100",      display_name="NVIDIA H100 (80 GB)",       vram_gb=80,  price_per_hour=3.95,  provider=Provider.MODAL),
    HardwareTier(slug="H200",      display_name="NVIDIA H200 (141 GB)",      vram_gb=141, price_per_hour=4.54,  provider=Provider.MODAL),
    HardwareTier(slug="B200",      display_name="NVIDIA B200 (~180 GB)",     vram_gb=180, price_per_hour=6.25,  provider=Provider.MODAL),
]


def _to_instance_info(info: ModalInstanceInfo, model_repo_id: str = "") -> InstanceInfo:
    return InstanceInfo(
        id=info.app_name,
        name=info.app_name,
        provider=Provider.MODAL,
        hardware_slug=info.gpu,
        model_repo_id=model_repo_id or info.model,
        status=info.status,
        endpoint_url=info.endpoint_url,
        region="modal-cloud",
    )


class ModalProvider(GpuProvider):

    async def list_hardware(self) -> list[HardwareTier]:
        return MODAL_HARDWARE

    async def create_instance(self, request: GpuProvisionRequest) -> InstanceInfo:
        info = await deploy_vllm_app(
            gpu=request.hardware_slug,
            model=request.model_repo_id,
            app_name=request.instance_name,
        )
        return _to_instance_info(info, request.model_repo_id)

    async def get_instance(self, instance_id: str) -> InstanceInfo:
        import httpx
        apps = await list_apps()
        for a in apps:
            if a["app_name"] == instance_id:
                # Probe the endpoint
                try:
                    async with httpx.AsyncClient(timeout=5) as client:
                        resp = await client.get(f"{a['endpoint_url']}/health")
                    status = "running" if resp.status_code == 200 else "degraded"
                except Exception:
                    status = "unreachable"
                return InstanceInfo(
                    id=a["app_name"],
                    name=a["app_name"],
                    provider=Provider.MODAL,
                    hardware_slug=a["gpu"],
                    model_repo_id=a["model"],
                    status=status,
                    endpoint_url=a["endpoint_url"],
                    region="modal-cloud",
                )
        raise ValueError(f"No Modal app '{instance_id}' in local state.")

    async def destroy_instance(self, instance_id: str) -> bool:
        await stop_app(instance_id)
        return True

    async def list_instances(self) -> list[InstanceInfo]:
        apps = await list_apps()
        return [
            InstanceInfo(
                id=a["app_name"],
                name=a["app_name"],
                provider=Provider.MODAL,
                hardware_slug=a["gpu"],
                model_repo_id=a["model"],
                status=a.get("status", "deployed"),
                endpoint_url=a["endpoint_url"],
                region="modal-cloud",
            )
            for a in apps
        ]
