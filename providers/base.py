from abc import ABC, abstractmethod


def classify_http_error(exc: Exception) -> str:
    """Return a human-readable error description, with extra detail for HTTP errors."""
    try:
        import httpx
        if isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code
            body = exc.response.text[:300]
            if status == 401:
                return f"authentication failed (401) — check provider credentials"
            if status == 403:
                return f"authorization denied (403) — insufficient permissions or quota exceeded"
            if status == 429:
                return f"rate limited (429) — too many requests, back off and retry"
            if 400 <= status < 500:
                return f"client error ({status}): {body}"
            if status >= 500:
                return f"provider server error ({status}): {body}"
    except ImportError:
        pass
    return str(exc)


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
