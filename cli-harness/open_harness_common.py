from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

DEFAULT_OPENROUTER_MODEL = "openai/gpt-oss-120b:free"
_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
_ENV_FILE = Path.home() / "dev" / ".env"


@dataclass
class LaunchTarget:
    provider_name: str
    base_url: str
    model: str
    env_key_name: str
    env_key_value: str


def _read_env_file() -> dict[str, str]:
    result: dict[str, str] = {}
    if _ENV_FILE.exists():
        for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            result[k.strip()] = v.strip()
    return result


def _get_openrouter_key() -> str:
    return os.environ.get("OPENROUTER_API_KEY") or _read_env_file().get("OPENROUTER_API_KEY", "")


def _get_openrouter_base_url() -> str:
    return os.environ.get("OPENROUTER_BASE_URL") or _read_env_file().get("OPENROUTER_BASE_URL", _DEFAULT_BASE_URL)


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


def resolve_locked_model(requested_model: str = "") -> str:
    normalized = _strip_openrouter_prefix(requested_model)
    if normalized and normalized != DEFAULT_OPENROUTER_MODEL:
        raise RuntimeError(
            f"Model override '{requested_model}' is not allowed. "
            f"This launcher is locked to '{DEFAULT_OPENROUTER_MODEL}'."
        )
    return DEFAULT_OPENROUTER_MODEL


def openrouter_target() -> LaunchTarget:
    key = _get_openrouter_key()
    if not key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not configured. Set it in environment or ~/dev/.env first."
        )
    return LaunchTarget(
        provider_name="openrouter",
        base_url=normalize_base_url(_get_openrouter_base_url()),
        model=DEFAULT_OPENROUTER_MODEL,
        env_key_name="OPENROUTER_API_KEY",
        env_key_value=key,
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
    Run an interactive CLI command preserving terminal controls on Windows and Unix.
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
