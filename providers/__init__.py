from providers.base import GpuProvider
from providers.hf_provider import HuggingFaceProvider
from providers.do_provider import DigitalOceanProvider
from models import Provider

PROVIDER_MAP: dict[Provider, type[GpuProvider]] = {
    Provider.HUGGINGFACE: HuggingFaceProvider,
    Provider.DIGITALOCEAN: DigitalOceanProvider,
}

__all__ = ["GpuProvider", "HuggingFaceProvider", "DigitalOceanProvider", "PROVIDER_MAP"]
