from abc import ABC, abstractmethod

from models import GpuProvisionRequest, HardwareTier, InstanceInfo


class GpuProvider(ABC):

    @abstractmethod
    async def list_hardware(self) -> list[HardwareTier]:
        """Return available hardware tiers for this provider."""
        ...

    @abstractmethod
    async def create_instance(self, request: GpuProvisionRequest) -> InstanceInfo:
        """Create and return a GPU instance."""
        ...

    @abstractmethod
    async def get_instance(self, instance_id: str) -> InstanceInfo:
        """Fetch current state of an instance by ID."""
        ...

    @abstractmethod
    async def destroy_instance(self, instance_id: str) -> bool:
        """Destroy an instance. Returns True on success."""
        ...

    @abstractmethod
    async def list_instances(self) -> list[InstanceInfo]:
        """List all active instances for this provider."""
        ...
