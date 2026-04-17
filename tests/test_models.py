"""Tests for Pydantic model validation."""
import pytest
from pydantic import ValidationError

from models import GpuProvisionRequest, Provider


def _valid_request(**overrides) -> dict:
    base = {
        "provider": Provider.MODAL,
        "hardware_slug": "H100",
        "model_repo_id": "Qwen/Qwen3-8B",
        "instance_name": "test-instance-01",
    }
    return {**base, **overrides}


class TestHardwareSlug:
    def test_valid_slugs(self):
        for slug in ("H100", "nvidia-t4-x1", "gpu-h100x1-80gb", "A100-80GB", "T4.small"):
            req = GpuProvisionRequest(**_valid_request(hardware_slug=slug))
            assert req.hardware_slug == slug

    def test_rejects_empty(self):
        with pytest.raises(ValidationError, match="hardware_slug"):
            GpuProvisionRequest(**_valid_request(hardware_slug=""))

    def test_rejects_leading_hyphen(self):
        with pytest.raises(ValidationError, match="hardware_slug"):
            GpuProvisionRequest(**_valid_request(hardware_slug="-bad"))

    def test_rejects_special_chars(self):
        with pytest.raises(ValidationError, match="hardware_slug"):
            GpuProvisionRequest(**_valid_request(hardware_slug="bad slug!"))


class TestModelRepoId:
    def test_valid_repo_ids(self):
        for repo in ("Qwen/Qwen3-8B", "google/gemma-2-2b-it", "meta-llama/Llama-3.1-8B-Instruct"):
            req = GpuProvisionRequest(**_valid_request(model_repo_id=repo))
            assert req.model_repo_id == repo

    def test_rejects_no_slash(self):
        with pytest.raises(ValidationError, match="owner/model"):
            GpuProvisionRequest(**_valid_request(model_repo_id="no-slash-here"))

    def test_rejects_empty(self):
        with pytest.raises(ValidationError, match="model_repo_id"):
            GpuProvisionRequest(**_valid_request(model_repo_id=""))

    def test_rejects_double_slash(self):
        with pytest.raises(ValidationError, match="owner/model"):
            GpuProvisionRequest(**_valid_request(model_repo_id="a/b/c"))


class TestInstanceName:
    def test_valid_names(self):
        for name in ("my-instance", "gpu-skill-01", "ab"):
            req = GpuProvisionRequest(**_valid_request(instance_name=name))
            assert req.instance_name == name

    def test_rejects_uppercase(self):
        with pytest.raises(ValidationError, match="instance_name"):
            GpuProvisionRequest(**_valid_request(instance_name="My-Instance"))

    def test_rejects_leading_hyphen(self):
        with pytest.raises(ValidationError, match="instance_name"):
            GpuProvisionRequest(**_valid_request(instance_name="-bad"))

    def test_rejects_trailing_hyphen(self):
        with pytest.raises(ValidationError, match="instance_name"):
            GpuProvisionRequest(**_valid_request(instance_name="bad-"))

    def test_rejects_too_short(self):
        with pytest.raises(ValidationError, match="instance_name"):
            GpuProvisionRequest(**_valid_request(instance_name="a"))

    def test_rejects_too_long(self):
        with pytest.raises(ValidationError, match="instance_name"):
            GpuProvisionRequest(**_valid_request(instance_name="a" * 51))


class TestMaxDeploymentHours:
    def test_default_is_8(self):
        req = GpuProvisionRequest(**_valid_request())
        assert req.max_deployment_hours == 8

    def test_accepts_valid_range(self):
        GpuProvisionRequest(**_valid_request(max_deployment_hours=1))
        GpuProvisionRequest(**_valid_request(max_deployment_hours=72))

    def test_rejects_zero(self):
        with pytest.raises(ValidationError):
            GpuProvisionRequest(**_valid_request(max_deployment_hours=0))

    def test_rejects_over_72(self):
        with pytest.raises(ValidationError):
            GpuProvisionRequest(**_valid_request(max_deployment_hours=73))


class TestProviderEnum:
    def test_all_expected_providers_exist(self):
        for name in ("huggingface", "digitalocean", "modal", "openrouter", "amd"):
            assert Provider(name) is not None

    def test_amd_in_enum(self):
        assert Provider.AMD.value == "amd"
