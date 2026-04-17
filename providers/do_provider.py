from __future__ import annotations

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings
from do_bootstrap import (
    DO_API,
    DropletInfo,
    _headers,
    create_droplet,
    find_existing_droplet,
    resolve_token,
)
from models import GpuProvisionRequest, HardwareTier, InstanceInfo, Provider
from providers.base import GpuProvider


def _to_instance_info(d: DropletInfo, model_repo_id: str = "") -> InstanceInfo:
    return InstanceInfo(
        id=str(d.id),
        name=d.name,
        provider=Provider.DIGITALOCEAN,
        hardware_slug=d.size,
        model_repo_id=model_repo_id,
        status=d.status,
        endpoint_url=d.ip,
        region=d.region,
    )


class DigitalOceanProvider(GpuProvider):

    def __init__(self) -> None:
        self.token = resolve_token()

    async def list_hardware(self) -> list[HardwareTier]:
        async with httpx.AsyncClient(headers=_headers(self.token), timeout=15) as client:
            resp = await client.get(f"{DO_API}/sizes?per_page=200")
            resp.raise_for_status()

        tiers: list[HardwareTier] = []
        for size in resp.json().get("sizes", []):
            if "gpu" not in size["slug"] or not size.get("regions"):
                continue
            tiers.append(
                HardwareTier(
                    slug=size["slug"],
                    display_name=size.get("description", size["slug"]),
                    vram_gb=0,
                    price_per_hour=size.get("price_hourly", 0.0),
                    provider=Provider.DIGITALOCEAN,
                    region=size["regions"][0],
                )
            )
        return tiers

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=5, max=30))
    async def create_instance(self, request: GpuProvisionRequest) -> InstanceInfo:
        info = await create_droplet(
            size=request.hardware_slug,
            name=request.instance_name,
        )
        return _to_instance_info(info, request.model_repo_id)

    async def get_instance(self, instance_id: str) -> InstanceInfo:
        async with httpx.AsyncClient(headers=_headers(self.token), timeout=15) as client:
            resp = await client.get(f"{DO_API}/droplets/{instance_id}")
            resp.raise_for_status()
        d = resp.json()["droplet"]
        nets = d.get("networks", {}).get("v4", [])
        ip = next((n["ip_address"] for n in nets if n["type"] == "public"), "")
        return InstanceInfo(
            id=str(d["id"]),
            name=d["name"],
            provider=Provider.DIGITALOCEAN,
            hardware_slug=d["size_slug"],
            model_repo_id="",
            status=d["status"],
            endpoint_url=ip,
            region=d["region"]["slug"],
        )

    async def destroy_instance(self, instance_id: str) -> bool:
        async with httpx.AsyncClient(headers=_headers(self.token), timeout=15) as client:
            resp = await client.delete(f"{DO_API}/droplets/{instance_id}")
        return resp.status_code == 204

    async def list_instances(self) -> list[InstanceInfo]:
        async with httpx.AsyncClient(headers=_headers(self.token), timeout=15) as client:
            resp = await client.get(f"{DO_API}/droplets?tag_name=agent-harness&per_page=200")
            resp.raise_for_status()
        result = []
        for d in resp.json().get("droplets", []):
            nets = d.get("networks", {}).get("v4", [])
            ip = next((n["ip_address"] for n in nets if n["type"] == "public"), "")
            result.append(InstanceInfo(
                id=str(d["id"]),
                name=d["name"],
                provider=Provider.DIGITALOCEAN,
                hardware_slug=d["size_slug"],
                model_repo_id="",
                status=d["status"],
                endpoint_url=ip,
                region=d["region"]["slug"],
            ))
        return result
