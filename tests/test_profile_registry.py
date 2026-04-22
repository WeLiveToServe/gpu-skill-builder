import json

import pytest

from models import Provider
from profile_registry import DEFAULT_HARNESS_PROFILE_ID, load_profile_registry, resolve_runtime_selection


def test_load_registry_and_resolve_explicit_digitalocean_profile():
    registry = load_profile_registry()

    selection = resolve_runtime_selection(
        provider=Provider.DIGITALOCEAN,
        hardware_slug="gpu-h200x1-141gb",
        model_repo_id="openai/gpt-oss-120b",
        registry=registry,
    )

    assert selection.model_profile.id == "openai-gpt-oss-120b"
    assert selection.deployment_profile.id == "digitalocean-gpt-oss-120b-h200x1"
    assert selection.harness_profile.id == DEFAULT_HARNESS_PROFILE_ID
    assert selection.deployment_profile.served_model_name == "gpt-oss-120b"


def test_resolve_managed_generic_profile():
    selection = resolve_runtime_selection(
        provider=Provider.HUGGINGFACE,
        hardware_slug="nvidia-t4-x1",
        model_repo_id="google/gemma-2-2b-it",
    )

    assert selection.deployment_profile.id == "huggingface-managed-endpoint-generic"
    assert selection.deployment_profile.managed_by_provider is True
    assert selection.model_profile.id == "google-gemma-2-2b-it"


def test_invalid_deployment_reference_raises(tmp_path):
    models_dir = tmp_path / "models"
    deployments_dir = tmp_path / "deployments"
    harnesses_dir = tmp_path / "harnesses"
    gateways_dir = tmp_path / "gateways"
    for directory in (models_dir, deployments_dir, harnesses_dir, gateways_dir):
        directory.mkdir(parents=True, exist_ok=True)

    (deployments_dir / "bad.json").write_text(
        json.dumps(
            {
                "kind": "deployment_profile",
                "id": "bad-deployment",
                "model_profile_id": "missing-model-profile",
                "provider": "digitalocean",
                "hardware_slug": "*",
                "runtime_kind": "vllm",
                "endpoint_class": "openai-compatible",
                "managed_by_provider": False,
                "served_model_name": "",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing model profile"):
        load_profile_registry(tmp_path)
