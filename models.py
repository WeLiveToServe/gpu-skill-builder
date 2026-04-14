from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Provider(str, Enum):
    HUGGINGFACE = "huggingface"
    DIGITALOCEAN = "digitalocean"


class HardwareTier(BaseModel):
    slug: str
    display_name: str
    vram_gb: int
    price_per_hour: float
    provider: Provider
    region: str = ""


class ModelRecommendation(BaseModel):
    repo_id: str
    display_name: str
    size_params: str
    vram_required_gb: int
    task: str = "text-generation"
    notes: str = ""


class GpuProvisionRequest(BaseModel):
    provider: Provider
    hardware_slug: str
    model_repo_id: str
    instance_name: str
    region: str = "us-east-1"
    max_deployment_hours: int = Field(default=8, ge=1, le=72)


class InstanceInfo(BaseModel):
    id: str
    name: str
    provider: Provider
    hardware_slug: str
    model_repo_id: str
    status: str
    endpoint_url: str = ""
    region: str = ""
    created_at: str = ""


class GpuProvisionResult(BaseModel):
    success: bool
    instance: Optional[InstanceInfo] = None
    message: str = ""
