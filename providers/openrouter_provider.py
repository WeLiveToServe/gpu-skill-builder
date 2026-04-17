from __future__ import annotations

from config import settings
from models import GpuProvisionRequest, HardwareTier, InstanceInfo, Provider
from providers.base import GpuProvider

OPENROUTER_HARDWARE = [
    HardwareTier(
        slug="openrouter-default",
        display_name="OpenRouter Fallback (Serverless)",
        vram_gb=640,
        price_per_hour=0.0,
        provider=Provider.OPENROUTER,
        region="global",
    )
]


class OpenRouterProvider(GpuProvider):
    async def list_hardware(self) -> list[HardwareTier]:
        return OPENROUTER_HARDWARE

    async def create_instance(self, request: GpuProvisionRequest) -> InstanceInfo:
        if not settings.openrouter_api_key:
            raise RuntimeError("OPENROUTER_API_KEY is required for OpenRouter fallback.")
        model = request.model_repo_id or settings.openrouter_model
        return InstanceInfo(
            id=f"{request.instance_name}-openrouter-fallback",
            name=request.instance_name,
            provider=Provider.OPENROUTER,
            hardware_slug=request.hardware_slug or "openrouter-default",
            model_repo_id=model,
            status="running",
            endpoint_url=settings.openrouter_base_url.rstrip("/"),
            region="global",
        )

    async def get_instance(self, instance_id: str) -> InstanceInfo:
        return InstanceInfo(
            id=instance_id,
            name=instance_id,
            provider=Provider.OPENROUTER,
            hardware_slug="openrouter-default",
            model_repo_id=settings.openrouter_model,
            status="running",
            endpoint_url=settings.openrouter_base_url.rstrip("/"),
            region="global",
        )

    async def destroy_instance(self, instance_id: str) -> bool:
        return True

    async def list_instances(self) -> list[InstanceInfo]:
        return []
