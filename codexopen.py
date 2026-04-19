#!/usr/bin/env python3
"""
codexopen: Launch Codex wired to either OpenRouter or an active GPU endpoint.

Examples:
  python codexopen.py --openrouter
  python codexopen.py --activegpu
  python codexopen.py --activegpu --model google/gemma-4-31B-it
"""

from __future__ import annotations

import argparse
import asyncio
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from config import settings
from models import InstanceInfo, Provider
from providers import PROVIDER_MAP


ACTIVE_STATUSES = {"running", "deployed"}
GPU_PROVIDER_ORDER = (Provider.DIGITALOCEAN, Provider.MODAL, Provider.HUGGINGFACE)


@dataclass
class LaunchTarget:
    provider_name: str
    base_url: str
    model: str
    env_key_name: str
    env_key_value: str


def _normalize_base_url(url: str) -> str:
    u = url.rstrip("/")
    if u.endswith("/v1"):
        return u
    return f"{u}/v1"


def _pick_instance(instances: list[InstanceInfo]) -> InstanceInfo | None:
    for inst in instances:
        if inst.status in ACTIVE_STATUSES and inst.endpoint_url:
            return inst
    return None


async def _discover_active_gpu() -> LaunchTarget:
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
                base_url=_normalize_base_url(picked.endpoint_url),
                model=picked.model_repo_id or "q",
                env_key_name="GPU_ENDPOINT_API_KEY",
                env_key_value=os.environ.get("GPU_ENDPOINT_API_KEY", "dummy"),
            )
        except Exception as exc:  # pragma: no cover - network/provider variability
            errors.append(f"{provider.value}: {exc}")

    detail = "; ".join(errors) if errors else "no running/deployed instances found"
    raise RuntimeError(f"No active GPU endpoint detected ({detail}).")


def _openrouter_target() -> LaunchTarget:
    if not settings.openrouter_api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not configured. Set it in environment or .env first."
        )
    return LaunchTarget(
        provider_name="openrouter",
        base_url=_normalize_base_url(settings.openrouter_base_url),
        model=settings.openrouter_model or "openrouter/auto",
        env_key_name="OPENROUTER_API_KEY",
        env_key_value=settings.openrouter_api_key,
    )


def _build_codex_cmd(target: LaunchTarget, cwd: str, model_override: str | None) -> list[str]:
    model = model_override or target.model
    provider_id = "relay"

    return [
        "codex",
        "-c",
        f'model="{model}"',
        "-c",
        f'model_provider="{provider_id}"',
        "-c",
        (
            "model_providers.relay={"
            f'name="{target.provider_name}",'
            f'base_url="{target.base_url}",'
            f'env_key="{target.env_key_name}",'
            'wire_api="responses"'
            "}"
        ),
        "-C",
        cwd,
    ]


async def _resolve_target(use_openrouter: bool, use_active_gpu: bool) -> LaunchTarget:
    if use_openrouter:
        return _openrouter_target()
    if use_active_gpu:
        return await _discover_active_gpu()
    raise RuntimeError("One of --openrouter or --activegpu must be set.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch Codex against OpenRouter or active GPU endpoint.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--openrouter", action="store_true", help="Use OpenRouter endpoint from config.")
    mode.add_argument("--activegpu", action="store_true", help="Auto-detect active GPU endpoint across providers.")
    parser.add_argument("--model", default="", help="Optional model override.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print resolved target and Codex command without launching.",
    )
    args = parser.parse_args()

    try:
        target = asyncio.run(_resolve_target(args.openrouter, args.activegpu))
    except Exception as exc:
        print(f"[codexopen] {exc}", file=sys.stderr)
        return 1

    cwd = str(Path.cwd())
    cmd = _build_codex_cmd(target, cwd, args.model.strip() or None)

    env = os.environ.copy()
    env[target.env_key_name] = target.env_key_value

    print(f"[codexopen] provider={target.provider_name} base_url={target.base_url} model={args.model or target.model}")
    print(f"[codexopen] env_key={target.env_key_name}")
    print(f"[codexopen] cmd={' '.join(shlex.quote(c) for c in cmd)}")

    if args.dry_run:
        return 0

    # Replace process so interactive Codex session works naturally.
    os.execvpe(cmd[0], cmd, env)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
