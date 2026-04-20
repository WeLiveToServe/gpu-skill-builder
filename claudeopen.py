#!/usr/bin/env python3
"""
claudeopen: Launch Claude Code CLI routed to OpenRouter.
"""

from __future__ import annotations

import argparse
import os
import shlex
import sys
from pathlib import Path

from open_harness_common import openrouter_target, run_interactive


def _build_cmd(cwd: str, model: str, passthrough: list[str]) -> list[str]:
    cmd = ["claude", "--model", model, "--add-dir", cwd]
    if passthrough:
        cmd.extend(passthrough)
    return cmd


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch Claude Code against OpenRouter.")
    parser.add_argument("--model", default="", help="Optional model override.")
    parser.add_argument("--dry-run", action="store_true", help="Print resolved target and command without launching.")
    args, passthrough = parser.parse_known_args()

    try:
        target = openrouter_target()
    except Exception as exc:
        print(f"[claudeopen] {exc}", file=sys.stderr)
        return 1

    model = args.model.strip() or target.model
    cwd = str(Path.cwd())
    cmd = _build_cmd(cwd, model, passthrough)

    env = os.environ.copy()
    # Claude Code only reads ANTHROPIC_API_KEY (ignores ANTHROPIC_AUTH_TOKEN).
    # Setting it to the OpenRouter key + ANTHROPIC_BASE_URL routes requests to OpenRouter.
    # A one-time consent prompt may appear for the custom key — select "Yes".
    env["ANTHROPIC_API_KEY"] = target.env_key_value
    env["ANTHROPIC_BASE_URL"] = target.base_url

    print(f"[claudeopen] provider={target.provider_name} base_url={env['ANTHROPIC_BASE_URL']} model={model}")
    print("[claudeopen] env_key=ANTHROPIC_API_KEY (set to OpenRouter key)")
    print(f"[claudeopen] cmd={' '.join(shlex.quote(c) for c in cmd)}")

    if args.dry_run:
        return 0

    return run_interactive(cmd, env)


if __name__ == "__main__":
    raise SystemExit(main())
