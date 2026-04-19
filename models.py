from __future__ import annotations

import re
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class Provider(str, Enum):
    HUGGINGFACE = "huggingface"
    DIGITALOCEAN = "digitalocean"
    MODAL = "modal"
    OPENROUTER = "openrouter"
    AMD = "amd"


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

    @field_validator("hardware_slug")
    @classmethod
    def validate_hardware_slug(cls, v: str) -> str:
        if not re.match(r'^[\w][\w\-\.]*$', v):
            raise ValueError(f"hardware_slug '{v}' must start with alphanumeric and contain only letters, digits, hyphens, dots")
        return v

    @field_validator("model_repo_id")
    @classmethod
    def validate_model_repo_id(cls, v: str) -> str:
        if not re.match(r'^[\w][\w\-\.]*\/[\w][\w\-\.]*$', v):
            raise ValueError(f"model_repo_id '{v}' must be in 'owner/model' format (e.g. 'google/gemma-2-2b-it')")
        return v

    @field_validator("instance_name")
    @classmethod
    def validate_instance_name(cls, v: str) -> str:
        if not re.match(r'^[a-z0-9][a-z0-9\-]{0,48}[a-z0-9]$', v):
            raise ValueError(
                f"instance_name '{v}' must be 2-50 chars, lowercase alphanumeric and hyphens only, "
                "cannot start or end with a hyphen"
            )
        return v


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
    fallback_activated: bool = False
    fallback_provider: Optional[Provider] = None
    fallback_reason: str = ""
    primary_provider_error: Optional[str] = None
