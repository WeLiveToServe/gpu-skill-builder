#!/usr/bin/env python3
"""
codexopen: Launch Codex routed to OpenRouter.

NOTE: Codex v0.115+ removed wire_api="chat" support. Only wire_api="responses"
is supported, which is incompatible with OpenRouter's tool-type requirements
(openrouter:web_search, openrouter:datetime, etc.). This wrapper will likely
fail on first turn until Codex adds a way to disable built-in Responses tools
or OpenRouter relaxes its tool-type validation.
"""

from __future__ import annotations

import argparse
import os
import shlex
import sys
from pathlib import Path

from open_harness_common import LaunchTarget, openrouter_target, run_interactive


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch Codex routed to OpenRouter.")
    parser.add_argument("--model", default="", help="Optional model override.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print resolved target and Codex command without launching.",
    )
    args = parser.parse_args()

    try:
        target = openrouter_target()
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

    return run_interactive(cmd, env)


if __name__ == "__main__":
    raise SystemExit(main())
