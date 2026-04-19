from __future__ import annotations

import httpx
from modal.client import _Client
from modal_proto import api_pb2

from modal_bootstrap import (
    GPU_SLUG_MAP,
    ModalInstanceInfo,
    deploy_vllm_app,
    list_apps,
    normalize_gpu,
    resolve_modal_env,
    stop_app,
)
from models import GpuProvisionRequest, HardwareTier, InstanceInfo, Provider
from providers.base import GpuProvider

# Deterministic hardware catalog — no LLM involvement
MODAL_HARDWARE: list[HardwareTier] = [
    HardwareTier(slug="T4",        display_name="NVIDIA T4 (16 GB)",        vram_gb=16,  price_per_hour=0.59,  provider=Provider.MODAL),
    HardwareTier(slug="L4",        display_name="NVIDIA L4 (24 GB)",         vram_gb=24,  price_per_hour=0.80,  provider=Provider.MODAL),
    HardwareTier(slug="A10",       display_name="NVIDIA A10 (24 GB)",        vram_gb=24,  price_per_hour=1.10,  provider=Provider.MODAL),
    HardwareTier(slug="L40S",      display_name="NVIDIA L40S (48 GB)",       vram_gb=48,  price_per_hour=1.95,  provider=Provider.MODAL),
    HardwareTier(slug="A100-40GB", display_name="NVIDIA A100 40 GB",         vram_gb=40,  price_per_hour=2.10,  provider=Provider.MODAL),
    HardwareTier(slug="A100-80GB", display_name="NVIDIA A100 80 GB",         vram_gb=80,  price_per_hour=2.50,  provider=Provider.MODAL),
    HardwareTier(slug="H100",      display_name="NVIDIA H100 (80 GB)",       vram_gb=80,  price_per_hour=3.95,  provider=Provider.MODAL),
    HardwareTier(slug="H200",      display_name="NVIDIA H200 (141 GB)",      vram_gb=141, price_per_hour=4.54,  provider=Provider.MODAL),
    HardwareTier(slug="B200",      display_name="NVIDIA B200 (~180 GB)",     vram_gb=180, price_per_hour=6.25,  provider=Provider.MODAL),
]


def _to_instance_info(info: ModalInstanceInfo, model_repo_id: str = "") -> InstanceInfo:
    return InstanceInfo(
        id=info.app_name,
        name=info.app_name,
        provider=Provider.MODAL,
        hardware_slug=info.gpu,
        model_repo_id=model_repo_id or info.model,
        status=info.status,
        endpoint_url=info.endpoint_url,
        region="modal-cloud",
    )


async def _probe_modal_status(endpoint_url: str) -> str:
    """
    Probe Modal web endpoint and infer runtime state.

    Returns one of:
    - running
    - scaled_to_zero
    - invalid_endpoint
    - degraded
    - unreachable
    """
    if not endpoint_url:
        return "unreachable"

    try:
        async with httpx.AsyncClient(timeout=6) as client:
            resp = await client.get(f"{endpoint_url.rstrip('/')}/health")
        if resp.status_code == 200:
            return "running"
        if resp.status_code == 404:
            body = (resp.text or "").lower()
            if "app for invoked web endpoint is stopped" in body:
                return "scaled_to_zero"
            if "invalid function call" in body:
                return "invalid_endpoint"
            return "degraded"
        if resp.status_code in (401, 403, 429):
            # Endpoint is reachable; these are often auth/rate-limit overlays.
            return "running"
        return "degraded"
    except Exception:
        return "unreachable"


async def get_modal_account_gpu_activity(environment_name: str = "") -> dict[str, int | bool]:
    """
    Query Modal account/workspace directly and summarize active GPU workload.

    This is account-wide and does not rely on local `.modal_state.json`.
    """
    env = resolve_modal_env()
    client = await _Client.from_credentials(env["MODAL_TOKEN_ID"], env["MODAL_TOKEN_SECRET"])
    try:
        apps_resp = await client.stub.AppList(api_pb2.AppListRequest(environment_name=environment_name))
        total_apps = len(apps_resp.apps)
        active_gpu_apps = 0
        active_gpu_tasks = 0
        stopped_apps = 0

        for app in apps_resp.apps:
            if app.state == api_pb2.APP_STATE_STOPPED:
                stopped_apps += 1

            if app.n_running_tasks <= 0:
                continue

            task_resp = await client.stub.TaskList(
                api_pb2.TaskListRequest(environment_name=environment_name, app_id=app.app_id)
            )
            running_gpu_for_app = 0
            for task in task_resp.tasks:
                is_running = task.finished_at == 0
                has_gpu = bool(task.gpu_type) or bool(getattr(task.gpu_config, "gpu_type", ""))
                has_gpu = has_gpu or getattr(task.gpu_config, "count", 0) > 0
                if is_running and has_gpu:
                    running_gpu_for_app += 1

            if running_gpu_for_app > 0:
                active_gpu_apps += 1
                active_gpu_tasks += running_gpu_for_app

        return {
            "ok": True,
            "total_apps": total_apps,
            "stopped_apps": stopped_apps,
            "active_gpu_apps": active_gpu_apps,
            "active_gpu_tasks": active_gpu_tasks,
        }
    finally:
        await client._close()


class ModalProvider(GpuProvider):

    async def list_hardware(self) -> list[HardwareTier]:
        return MODAL_HARDWARE

    async def create_instance(self, request: GpuProvisionRequest) -> InstanceInfo:
        info = await deploy_vllm_app(
            gpu=request.hardware_slug,
            model=request.model_repo_id,
            app_name=request.instance_name,
        )
        return _to_instance_info(info, request.model_repo_id)

    async def get_instance(self, instance_id: str) -> InstanceInfo:
        apps = await list_apps()
        for a in apps:
            if a["app_name"] == instance_id:
                status = await _probe_modal_status(a["endpoint_url"])
                return InstanceInfo(
                    id=a["app_name"],
                    name=a["app_name"],
                    provider=Provider.MODAL,
                    hardware_slug=a["gpu"],
                    model_repo_id=a["model"],
                    status=status,
                    endpoint_url=a["endpoint_url"],
                    region="modal-cloud",
                )
        raise ValueError(f"No Modal app '{instance_id}' in local state.")

    async def destroy_instance(self, instance_id: str) -> bool:
        await stop_app(instance_id)
        return True

    async def list_instances(self) -> list[InstanceInfo]:
        apps = await list_apps()
        instances: list[InstanceInfo] = []
        for a in apps:
            status = await _probe_modal_status(a["endpoint_url"])
            instances.append(
                InstanceInfo(
                    id=a["app_name"],
                    name=a["app_name"],
                    provider=Provider.MODAL,
                    hardware_slug=a["gpu"],
                    model_repo_id=a["model"],
                    status=status,
                    endpoint_url=a["endpoint_url"],
                    region="modal-cloud",
                )
            )
        return instances
