#!/usr/bin/env python3
"""
claudeopen: Launch Claude CLI wired to either OpenRouter or an active GPU endpoint.
"""

from __future__ import annotations

import argparse
import os
import shlex
import sys
from pathlib import Path

from open_harness_common import resolve_target_sync, run_interactive, strip_v1


def _build_cmd(cwd: str, model: str | None, passthrough: list[str]) -> list[str]:
    cmd = [
        "claude",
        "--model",
        model or "q",
        "--add-dir",
        cwd,
    ]
    if passthrough:
        cmd.extend(passthrough)
    return cmd


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch Claude against OpenRouter or active GPU endpoint.")
    mode = parser.add_mutually_exclusive_group(required=False)
    mode.add_argument("--openrouter", action="store_true", help="Use OpenRouter endpoint from config.")
    mode.add_argument("--activegpu", action="store_true", help="Auto-detect active GPU endpoint across providers.")
    parser.add_argument("--model", default="", help="Optional model override.")
    parser.add_argument("--dry-run", action="store_true", help="Print resolved target and command without launching.")
    args, passthrough = parser.parse_known_args()
    if not args.openrouter and not args.activegpu:
        args.openrouter = True

    try:
        target = resolve_target_sync(args.openrouter, args.activegpu)
    except Exception as exc:
        print(f"[claudeopen] {exc}", file=sys.stderr)
        return 1

    model = args.model.strip() or target.model
    cwd = str(Path.cwd())
    cmd = _build_cmd(cwd, model, passthrough)

    env = os.environ.copy()
    env[target.env_key_name] = target.env_key_value
    env["ANTHROPIC_AUTH_TOKEN"] = target.env_key_value
    env["ANTHROPIC_BASE_URL"] = (
        target.base_url if target.provider_name == "openrouter" else strip_v1(target.base_url)
    )
    # Prevent Claude's API-key consent prompt by avoiding ANTHROPIC_API_KEY for this wrapper.
    env.pop("ANTHROPIC_API_KEY", None)

    print(f"[claudeopen] provider={target.provider_name} base_url={env['ANTHROPIC_BASE_URL']} model={model}")
    print("[claudeopen] env_key=ANTHROPIC_AUTH_TOKEN")
    print(f"[claudeopen] cmd={' '.join(shlex.quote(c) for c in cmd)}")

    if args.dry_run:
        return 0

    return run_interactive(cmd, env)


if __name__ == "__main__":
    raise SystemExit(main())
