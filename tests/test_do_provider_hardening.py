"""Regression tests for DO provider hardening and remote vLLM safety."""

import asyncio
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from do_bootstrap import DropletInfo
from models import GpuProvisionRequest, Provider
from providers.do_provider import DigitalOceanProvider
from remote_vllm import deploy_vllm_remote


def run(coro):
    return asyncio.run(coro)


def _request() -> GpuProvisionRequest:
    return GpuProvisionRequest(
        provider=Provider.DIGITALOCEAN,
        hardware_slug="gpu-h100x1-80gb",
        model_repo_id="google/gemma-2-2b-it",
        instance_name="do-hardening-test",
        region="nyc1",
    )


class TestDoProviderCreate:
    def test_create_normalizes_status_persists_model_and_returns_full_endpoint(self):
        droplet = DropletInfo(
            id=123,
            name="do-hardening-test",
            ip="1.2.3.4",
            region="nyc1",
            size="gpu-h100x1-80gb",
            status="active",
        )
        req = _request()

        with patch("providers.do_provider.resolve_token", return_value="dop_v1_test"), \
             patch("providers.do_provider.create_droplet", new=AsyncMock(return_value=droplet)), \
             patch("providers.do_provider.deploy_vllm_remote", new=AsyncMock(return_value="http://1.2.3.4:8000")) as deploy_remote, \
             patch("providers.do_provider._load_state", return_value={}), \
             patch("providers.do_provider._save_state") as save_state:
            provider = DigitalOceanProvider()
            inst = run(provider.create_instance(req))

        assert inst.status == "running"
        assert inst.endpoint_url == "http://1.2.3.4:8000"
        assert inst.model_repo_id == req.model_repo_id
        assert inst.runtime_kind == "vllm"
        assert inst.endpoint_class == "openai-compatible"
        assert inst.deployment_profile_id == "digitalocean-vllm-generic"
        assert inst.model_profile_id == "google-gemma-2-2b-it"
        assert inst.harness_profile_id == "openai-compatible-generic"
        assert inst.served_model_name == req.model_repo_id
        call = deploy_remote.await_args
        assert call.kwargs["deployment_profile"].id == "digitalocean-vllm-generic"
        assert call.kwargs["model_profile"].id == "google-gemma-2-2b-it"
        saved_state = save_state.call_args.args[0]
        assert saved_state["droplet_models"] == {"123": req.model_repo_id}
        assert saved_state["droplet_runtime_meta"]["123"]["runtime_kind"] == "vllm"
        assert saved_state["droplet_runtime_meta"]["123"]["deployment_profile_id"] == "digitalocean-vllm-generic"


@dataclass
class _FakeResponse:
    status_code: int
    payload: dict

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self.payload


class _FakeAsyncClient:
    def __init__(self, response_get: _FakeResponse | None = None, response_delete: _FakeResponse | None = None):
        self._response_get = response_get
        self._response_delete = response_delete

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def get(self, _url):
        return self._response_get

    async def delete(self, _url):
        return self._response_delete


class TestDoProviderReadAndDestroy:
    def test_get_and_list_hydrate_model_normalize_status_and_endpoint(self):
        get_payload = {
            "droplet": {
                "id": 321,
                "name": "gpu-a",
                "size_slug": "gpu-h100x1-80gb",
                "status": "active",
                "region": {"slug": "nyc1"},
                "networks": {"v4": [{"type": "public", "ip_address": "2.3.4.5"}]},
            }
        }
        list_payload = {
            "droplets": [
                {
                    "id": 321,
                    "name": "gpu-a",
                    "size_slug": "gpu-h100x1-80gb",
                    "status": "active",
                    "region": {"slug": "nyc1"},
                    "networks": {"v4": [{"type": "public", "ip_address": "2.3.4.5"}]},
                },
                {
                    "id": 322,
                    "name": "gpu-b",
                    "size_slug": "gpu-h100x1-80gb",
                    "status": "new",
                    "region": {"slug": "sfo3"},
                    "networks": {"v4": [{"type": "public", "ip_address": "6.7.8.9"}]},
                },
            ]
        }

        def client_factory(*_args, **_kwargs):
            mock = MagicMock()
            # Use two clients in sequence: get_instance then list_instances
            if not hasattr(client_factory, "count"):
                client_factory.count = 0
            client_factory.count += 1
            if client_factory.count == 1:
                return _FakeAsyncClient(response_get=_FakeResponse(200, get_payload))
            return _FakeAsyncClient(response_get=_FakeResponse(200, list_payload))

        with patch("providers.do_provider.resolve_token", return_value="dop_v1_test"), \
             patch("providers.do_provider.httpx.AsyncClient", side_effect=client_factory), \
             patch(
                 "providers.do_provider._load_state",
                 return_value={
                     "droplet_models": {"321": "google/gemma-2-2b-it", "322": "meta-llama/Llama-3.1-8B-Instruct"},
                     "droplet_runtime_meta": {
                         "321": {
                             "model_repo_id": "google/gemma-2-2b-it",
                             "runtime_kind": "vllm",
                             "endpoint_class": "openai-compatible",
                             "managed_by_provider": False,
                             "deployment_profile_id": "digitalocean-vllm-generic",
                             "model_profile_id": "google-gemma-2-2b-it",
                             "harness_profile_id": "openai-compatible-generic",
                             "served_model_name": "google/gemma-2-2b-it",
                         }
                     },
                 },
             ):
            provider = DigitalOceanProvider()
            got = run(provider.get_instance("321"))
            listed = run(provider.list_instances())

        assert got.status == "running"
        assert got.endpoint_url == "http://2.3.4.5:8000"
        assert got.model_repo_id == "google/gemma-2-2b-it"
        assert got.runtime_kind == "vllm"
        assert got.deployment_profile_id == "digitalocean-vllm-generic"

        assert len(listed) == 2
        assert listed[0].status == "running"
        assert listed[1].status == "pending"
        assert listed[0].endpoint_url == "http://2.3.4.5:8000"
        assert listed[1].endpoint_url == "http://6.7.8.9:8000"
        assert listed[1].model_repo_id == "meta-llama/Llama-3.1-8B-Instruct"
        assert listed[1].runtime_kind == "vllm"
        assert listed[1].endpoint_class == "openai-compatible"

    def test_destroy_success_cleans_saved_model_mapping(self):
        delete_resp = _FakeResponse(204, {})
        with patch("providers.do_provider.resolve_token", return_value="dop_v1_test"), \
             patch("providers.do_provider.httpx.AsyncClient", return_value=_FakeAsyncClient(response_delete=delete_resp)), \
             patch(
                 "providers.do_provider._load_state",
                 return_value={
                     "droplet_models": {"123": "google/gemma-2-2b-it"},
                     "droplet_runtime_meta": {"123": {"runtime_kind": "vllm"}},
                 },
             ), \
             patch("providers.do_provider._save_state") as save_state:
            provider = DigitalOceanProvider()
            destroyed = run(provider.destroy_instance("123"))

        assert destroyed is True
        save_state.assert_called_with({"droplet_models": {}, "droplet_runtime_meta": {}})


class _FakeProc:
    def __init__(self, output: bytes):
        self.returncode = 0
        self._output = output

    async def communicate(self, input=None):
        return self._output, b""


class TestRemoteVllmSafety:
    def test_rejects_unsafe_model_id_before_ssh(self):
        with patch("remote_vllm.asyncio.create_subprocess_exec", new=AsyncMock()) as spawn:
            with pytest.raises(ValueError, match="model_id"):
                run(
                    deploy_vllm_remote(
                        ip="1.2.3.4",
                        model_id="bad\nmodel",
                        ssh_key_path="C:/tmp/key",
                    )
                )
        spawn.assert_not_called()

    def test_rejects_unsafe_token_before_ssh(self):
        with patch("remote_vllm.asyncio.create_subprocess_exec", new=AsyncMock()) as spawn:
            with pytest.raises(ValueError, match="hf_token"):
                run(
                    deploy_vllm_remote(
                        ip="1.2.3.4",
                        model_id="google/gemma-2-2b-it",
                        ssh_key_path="C:/tmp/key",
                        hf_token="bad token",
                    )
                )
        spawn.assert_not_called()

    def test_uses_positional_args_and_static_script(self):
        spawn = AsyncMock(return_value=_FakeProc(b"MODEL_SWAP_OK\n"))
        with patch("remote_vllm.asyncio.create_subprocess_exec", new=spawn):
            endpoint = run(
                deploy_vllm_remote(
                    ip="1.2.3.4",
                    model_id="google/gemma-2-2b-it",
                    ssh_key_path="C:/tmp/key",
                    hf_token="hf_xxx",
                )
            )

        assert endpoint == "http://1.2.3.4:8000"
        call_args = spawn.await_args.args
        assert call_args[0] == "ssh"
        assert "--" in call_args
        assert "google/gemma-2-2b-it" in call_args
