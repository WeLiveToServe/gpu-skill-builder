from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import time
from dataclasses import dataclass

from config import settings
from models import InstanceInfo, Provider
from providers import PROVIDER_MAP

ACTIVE_STATUSES = {"running", "deployed"}
GPU_PROVIDER_ORDER = (Provider.DIGITALOCEAN, Provider.MODAL, Provider.HUGGINGFACE)
# Looked up from OpenRouter live models list (paid): https://openrouter.ai/api/v1/models
DEFAULT_OPENROUTER_MODEL = "qwen/qwen3.5-35b-a3b"


@dataclass
class LaunchTarget:
    provider_name: str
    base_url: str
    model: str
    env_key_name: str
    env_key_value: str


def normalize_base_url(url: str) -> str:
    u = url.rstrip("/")
    if u.endswith("/v1"):
        return u
    return f"{u}/v1"


def strip_v1(url: str) -> str:
    u = url.rstrip("/")
    if u.endswith("/v1"):
        return u[:-3]
    return u


def resolve_openrouter_model() -> str:
    configured = (settings.openrouter_model or "").strip()
    if not configured or configured == "openrouter/auto":
        return DEFAULT_OPENROUTER_MODEL
    return configured


def _pick_instance(instances: list[InstanceInfo]) -> InstanceInfo | None:
    for inst in instances:
        if inst.status in ACTIVE_STATUSES and inst.endpoint_url:
            return inst
    return None


async def discover_active_gpu() -> LaunchTarget:
    errors: list[str] = []
    for provider in GPU_PROVIDER_ORDER:
        provider_cls = PROVIDER_MAP.get(provider)
        if not provider_cls:
            continue
        try:
            instances = await provider_cls().list_instances()
            picked = _pick_instance(instances)
            if not picked:
                continue
            return LaunchTarget(
                provider_name=provider.value,
                base_url=normalize_base_url(picked.endpoint_url),
                model=picked.model_repo_id or "q",
                env_key_name="GPU_ENDPOINT_API_KEY",
                env_key_value=os.environ.get("GPU_ENDPOINT_API_KEY", "dummy"),
            )
        except Exception as exc:  # pragma: no cover - provider/network variability
            errors.append(f"{provider.value}: {exc}")
    detail = "; ".join(errors) if errors else "no running/deployed instances found"
    raise RuntimeError(f"No active GPU endpoint detected ({detail}).")


def openrouter_target() -> LaunchTarget:
    if not settings.openrouter_api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not configured. Set it in environment or .env first."
        )
    return LaunchTarget(
        provider_name="openrouter",
        base_url=normalize_base_url(settings.openrouter_base_url),
        model=resolve_openrouter_model(),
        env_key_name="OPENROUTER_API_KEY",
        env_key_value=settings.openrouter_api_key,
    )


def resolve_target_sync(use_openrouter: bool, use_active_gpu: bool) -> LaunchTarget:
    if use_openrouter:
        return openrouter_target()
    if use_active_gpu:
        return asyncio.run(discover_active_gpu())
    raise RuntimeError("One of --openrouter or --activegpu must be set.")


def _resolve_windows_cmd(cmd: list[str]) -> list[str]:
    """Resolve .cmd executables on Windows — CreateProcess can't run .cmd without the shell."""
    exe = shutil.which(cmd[0])
    if exe is None:
        return cmd
    if exe.lower().endswith(".cmd"):
        return ["cmd", "/c", exe] + cmd[1:]
    return [exe] + cmd[1:]


def run_interactive(cmd: list[str], env: dict[str, str]) -> int:
    """
    Run an interactive CLI command in a way that preserves terminal controls
    on Windows (Enter/Ctrl+C) and Unix.
    """
    if os.name == "nt":
        cmd = _resolve_windows_cmd(cmd)
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        proc = subprocess.Popen(cmd, env=env, shell=False, creationflags=creationflags)
        try:
            return int(proc.wait())
        except KeyboardInterrupt:
            try:
                ctrl_break = getattr(subprocess, "CTRL_BREAK_EVENT", None)
                if ctrl_break is not None:
                    proc.send_signal(ctrl_break)
                    for _ in range(20):
                        if proc.poll() is not None:
                            return int(proc.returncode)
                        time.sleep(0.1)
            except Exception:
                pass
            try:
                proc.terminate()
                for _ in range(20):
                    if proc.poll() is not None:
                        return int(proc.returncode)
                    time.sleep(0.1)
            except Exception:
                pass
            try:
                proc.kill()
            except Exception:
                pass
            return 130

    os.execvpe(cmd[0], cmd, env)
    return 0
