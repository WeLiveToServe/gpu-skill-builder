#!/usr/bin/env python3
"""
codexopen: Launch Codex routed to OpenRouter.

This wrapper enforces OpenRouter compatibility mode by disabling Codex features
that inject incompatible Responses tool payloads.
"""

from __future__ import annotations

import argparse
import os
import shlex
import sys
from pathlib import Path

from open_harness_common import LaunchTarget, openrouter_target, resolve_locked_model, run_interactive

COMPAT_DISABLE_FEATURES = [
    "apps",
    "plugins",
    "personality",
    "multi_agent",
    "skill_mcp_dependency_install",
    "tool_suggest",
    "workspace_dependencies",
]


def _build_codex_cmd(target: LaunchTarget, cwd: str, model: str, passthrough: list[str]) -> list[str]:
    provider_id = "relay"
    cmd = [
        "codex",
        "-c",
        f'model="{model}"',
        "-c",
        f'model_provider="{provider_id}"',
        "-c",
        f'model_providers.{provider_id}.name="{target.provider_name}"',
        "-c",
        f'model_providers.{provider_id}.base_url="{target.base_url}"',
        "-c",
        f'model_providers.{provider_id}.env_key="{target.env_key_name}"',
        "-c",
        f'model_providers.{provider_id}.wire_api="responses"',
        "-C",
        cwd,
    ]
    for feature in COMPAT_DISABLE_FEATURES:
        cmd.extend(["--disable", feature])
    if passthrough:
        cmd.extend(passthrough)
    return cmd


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch Codex routed to OpenRouter.")
    parser.add_argument("--model", default="", help="Ignored unless set to locked model openai/gpt-oss-120b:free.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print resolved target and Codex command without launching.",
    )
    args, passthrough = parser.parse_known_args()

    try:
        target = openrouter_target()
        model = resolve_locked_model(args.model)
    except Exception as exc:
        print(f"[codexopen] {exc}", file=sys.stderr)
        return 1

    cwd = str(Path.cwd())
    cmd = _build_codex_cmd(target, cwd, model, passthrough)

    env = os.environ.copy()
    env[target.env_key_name] = target.env_key_value

    print(f"[codexopen] provider={target.provider_name} base_url={target.base_url} model={model}", file=sys.stderr)
    print(f"[codexopen] env_key={target.env_key_name}", file=sys.stderr)
    print(f"[codexopen] compat_disables={','.join(COMPAT_DISABLE_FEATURES)}", file=sys.stderr)
    print(f"[codexopen] cmd={' '.join(shlex.quote(c) for c in cmd)}", file=sys.stderr)

    if args.dry_run:
        return 0

    return run_interactive(cmd, env)


if __name__ == "__main__":
    raise SystemExit(main())
