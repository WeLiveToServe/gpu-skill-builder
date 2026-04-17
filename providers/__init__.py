from providers.base import GpuProvider
from providers.hf_provider import HuggingFaceProvider
from providers.do_provider import DigitalOceanProvider
from providers.modal_provider import ModalProvider
from models import Provider

PROVIDER_MAP: dict[Provider, type[GpuProvider]] = {
    Provider.HUGGINGFACE: HuggingFaceProvider,
    Provider.DIGITALOCEAN: DigitalOceanProvider,
    Provider.MODAL: ModalProvider,
}

__all__ = ["GpuProvider", "HuggingFaceProvider", "DigitalOceanProvider", "ModalProvider", "PROVIDER_MAP"]
