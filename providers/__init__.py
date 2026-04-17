from providers.base import GpuProvider
from providers.hf_provider import HuggingFaceProvider
from providers.do_provider import DigitalOceanProvider
from providers.modal_provider import ModalProvider
from providers.openrouter_provider import OpenRouterProvider
from models import Provider

PROVIDER_MAP: dict[Provider, type[GpuProvider]] = {
    Provider.HUGGINGFACE: HuggingFaceProvider,
    Provider.DIGITALOCEAN: DigitalOceanProvider,
    Provider.MODAL: ModalProvider,
    Provider.OPENROUTER: OpenRouterProvider,
}

__all__ = [
    "GpuProvider",
    "HuggingFaceProvider",
    "DigitalOceanProvider",
    "ModalProvider",
    "OpenRouterProvider",
    "PROVIDER_MAP",
]
