from __future__ import annotations

import httpx
from huggingface_hub import HfApi
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings
from models import GpuProvisionRequest, HardwareTier, InstanceInfo, Provider
from providers.base import GpuProvider

HF_API_BASE = "https://api.endpoints.huggingface.cloud/v2"

# Deterministic hardware catalog — no LLM involvement
HF_HARDWARE: list[HardwareTier] = [
    HardwareTier(slug="nvidia-t4-x1",    display_name="NVIDIA T4 (16 GB)",      vram_gb=16,  price_per_hour=0.60,  provider=Provider.HUGGINGFACE),
    HardwareTier(slug="nvidia-a10g-x1",  display_name="NVIDIA A10G (24 GB)",    vram_gb=24,  price_per_hour=1.00,  provider=Provider.HUGGINGFACE),
    HardwareTier(slug="nvidia-a10g-x4",  display_name="4× NVIDIA A10G (96 GB)", vram_gb=96,  price_per_hour=4.00,  provider=Provider.HUGGINGFACE),
    HardwareTier(slug="nvidia-a100-x1",  display_name="NVIDIA A100 (80 GB)",    vram_gb=80,  price_per_hour=4.00,  provider=Provider.HUGGINGFACE),
    HardwareTier(slug="nvidia-a100-x4",  display_name="4× NVIDIA A100 (320 GB)",vram_gb=320, price_per_hour=16.00, provider=Provider.HUGGINGFACE),
]


class HuggingFaceProvider(GpuProvider):

    def __init__(self) -> None:
        self.token = settings.hf_token
        self._api = HfApi(token=self.token)
        self._namespace: str | None = None

    @property
    def namespace(self) -> str:
        if not self._namespace:
            self._namespace = self._api.whoami()["name"]
        return self._namespace

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    async def list_hardware(self) -> list[HardwareTier]:
        return HF_HARDWARE

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def create_instance(self, request: GpuProvisionRequest) -> InstanceInfo:
        # "nvidia-t4-x1" → instanceType="nvidia-t4", instanceSize="x1"
        *type_parts, instance_size = request.hardware_slug.split("-")
        instance_type = "-".join(type_parts)

        payload = {
            "compute": {
                "accelerator": "gpu",
                "instanceSize": instance_size,
                "instanceType": instance_type,
                "scaling": {"maxReplica": 1, "minReplica": 0},
            },
            "model": {
                "framework": "pytorch",
                "image": {"huggingface": {}},
                "repository": request.model_repo_id,
                "revision": None,
                "task": "text-generation",
            },
            "name": request.instance_name,
            "provider": {"region": request.region, "vendor": "aws"},
            "type": "protected",
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{HF_API_BASE}/endpoint/{self.namespace}",
                headers=self._headers,
                json=payload,
                timeout=30.0,
            )
            resp.raise_for_status()

        return self._parse_endpoint(resp.json())

    async def get_instance(self, instance_id: str) -> InstanceInfo:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{HF_API_BASE}/endpoint/{self.namespace}/{instance_id}",
                headers=self._headers,
                timeout=15.0,
            )
            resp.raise_for_status()
        return self._parse_endpoint(resp.json())

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def destroy_instance(self, instance_id: str) -> bool:
        async with httpx.AsyncClient() as client:
            resp = await client.delete(
                f"{HF_API_BASE}/endpoint/{self.namespace}/{instance_id}",
                headers=self._headers,
                timeout=15.0,
            )
        return resp.status_code in (200, 204)

    async def list_instances(self) -> list[InstanceInfo]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{HF_API_BASE}/endpoint/{self.namespace}",
                headers=self._headers,
                timeout=15.0,
            )
            resp.raise_for_status()
        return [self._parse_endpoint(e) for e in resp.json().get("items", [])]

    def _parse_endpoint(self, data: dict) -> InstanceInfo:
        compute = data.get("compute", {})
        instance_type = compute.get("instanceType", "")
        instance_size = compute.get("instanceSize", "")
        slug = f"{instance_type}-{instance_size}" if instance_type else ""

        status_obj = data.get("status", {})
        if isinstance(status_obj, dict):
            status = status_obj.get("state", "unknown")
            endpoint_url = status_obj.get("url", "")
        else:
            status, endpoint_url = "unknown", ""

        return InstanceInfo(
            id=data.get("name", ""),
            name=data.get("name", ""),
            provider=Provider.HUGGINGFACE,
            hardware_slug=slug,
            model_repo_id=data.get("model", {}).get("repository", ""),
            status=status,
            endpoint_url=endpoint_url,
            region=data.get("provider", {}).get("region", ""),
            created_at=data.get("createdAt", ""),
        )
