from __future__ import annotations

import time

import digitalocean
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings
from models import GpuProvisionRequest, HardwareTier, InstanceInfo, Provider
from providers.base import GpuProvider

DO_SSH_KEY_NAME = "codex-do-oci-ampere"


class DigitalOceanProvider(GpuProvider):

    def __init__(self) -> None:
        self.token = settings.digitalocean_token
        if not self.token:
            raise ValueError("DIGITALOCEAN_TOKEN not set.")
        self.manager = digitalocean.Manager(token=self.token)

    async def list_hardware(self) -> list[HardwareTier]:
        all_sizes = self.manager.get_all_sizes()
        tiers: list[HardwareTier] = []
        for size in all_sizes:
            if "gpu" in size.slug or (hasattr(size, "gpu_info") and size.gpu_info):
                tiers.append(
                    HardwareTier(
                        slug=size.slug,
                        display_name=getattr(size, "description", size.slug),
                        vram_gb=0,  # DO API does not expose VRAM directly
                        price_per_hour=size.price_hourly,
                        provider=Provider.DIGITALOCEAN,
                        region=size.regions[0] if size.regions else "",
                    )
                )
        return tiers

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=5, max=30))
    async def create_instance(self, request: GpuProvisionRequest) -> InstanceInfo:
        keys = self.manager.get_all_sshkeys()
        ssh_key = next((k for k in keys if k.name == DO_SSH_KEY_NAME), None)
        if not ssh_key:
            raise ValueError(f"SSH key '{DO_SSH_KEY_NAME}' not found in DigitalOcean account.")

        droplet = digitalocean.Droplet(
            token=self.token,
            name=request.instance_name,
            region=request.region,
            image="ubuntu-24-04-x64",
            size_slug=request.hardware_slug,
            ssh_keys=[ssh_key],
            tags=["gpu-builder-skill"],
        )
        droplet.create()

        for action in droplet.get_actions():
            action.load()
            while action.status != "completed":
                time.sleep(10)
                action.load()

        droplet.load()
        return InstanceInfo(
            id=str(droplet.id),
            name=droplet.name,
            provider=Provider.DIGITALOCEAN,
            hardware_slug=droplet.size_slug,
            model_repo_id=request.model_repo_id,
            status=droplet.status,
            endpoint_url=droplet.ip_address or "",
            region=droplet.region["slug"],
        )

    async def get_instance(self, instance_id: str) -> InstanceInfo:
        droplet = self.manager.get_droplet(int(instance_id))
        return InstanceInfo(
            id=str(droplet.id),
            name=droplet.name,
            provider=Provider.DIGITALOCEAN,
            hardware_slug=droplet.size_slug,
            model_repo_id="",
            status=droplet.status,
            endpoint_url=droplet.ip_address or "",
            region=droplet.region["slug"],
        )

    async def destroy_instance(self, instance_id: str) -> bool:
        droplet = self.manager.get_droplet(int(instance_id))
        droplet.destroy()
        return True

    async def list_instances(self) -> list[InstanceInfo]:
        droplets = self.manager.get_all_droplets(tag_name="gpu-builder-skill")
        return [
            InstanceInfo(
                id=str(d.id),
                name=d.name,
                provider=Provider.DIGITALOCEAN,
                hardware_slug=d.size_slug,
                model_repo_id="",
                status=d.status,
                endpoint_url=d.ip_address or "",
                region=d.region["slug"],
            )
            for d in droplets
        ]
