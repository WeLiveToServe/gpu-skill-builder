from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass

from config import settings

DEFAULT_OPENROUTER_MODEL = "openai/gpt-oss-120b:free"
HARNESS_BASE_URL_ENV = "HARNESS_OPENROUTER_BASE_URL"
HARNESS_MODEL_ENV = "HARNESS_OPENROUTER_MODEL"
HARNESS_API_KEY_ENV = "HARNESS_OPENROUTER_API_KEY"


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


def _strip_openrouter_prefix(model: str) -> str:
    m = model.strip()
    if m.startswith("openrouter/"):
        return m[len("openrouter/"):]
    return m


def _process_override(name: str) -> str:
    return os.environ.get(name, "").strip()


def configured_openrouter_base_url() -> str:
    """
    Process-local harness overrides win so benchmark jobs can target a local
    tunnel without touching repo .env files or sibling repos.
    """
    return normalize_base_url(_process_override(HARNESS_BASE_URL_ENV) or settings.openrouter_base_url)


def configured_openrouter_api_key() -> str:
    return _process_override(HARNESS_API_KEY_ENV) or settings.openrouter_api_key


def configured_locked_model() -> str:
    return _strip_openrouter_prefix(_process_override(HARNESS_MODEL_ENV) or DEFAULT_OPENROUTER_MODEL)


def resolve_locked_model(requested_model: str = "") -> str:
    locked_model = configured_locked_model()
    normalized = _strip_openrouter_prefix(requested_model)
    if normalized and normalized != locked_model:
        raise RuntimeError(
            f"Model override '{requested_model}' is not allowed. "
            f"This launcher is locked to '{locked_model}'."
        )
    return locked_model


def openrouter_target() -> LaunchTarget:
    api_key = configured_openrouter_api_key()
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not configured. Set it in environment or .env first. "
            "For local benchmark routing, HARNESS_OPENROUTER_API_KEY is also supported."
        )
    return LaunchTarget(
        provider_name="openrouter",
        base_url=configured_openrouter_base_url(),
        model=configured_locked_model(),
        env_key_name="OPENROUTER_API_KEY",
        env_key_value=api_key,
    )


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
