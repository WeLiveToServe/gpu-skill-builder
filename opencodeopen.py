#!/usr/bin/env python3
"""
opencode wrapper:
- With --openrouter: launch OpenCode routed to OpenRouter.
- Without flags: pass through to the native opencode CLI unchanged.

NOTE: OpenCode does not have a built-in openrouter provider activated solely
by OPENROUTER_API_KEY. To use OpenRouter, add an 'openrouter' provider entry
to ~/.config/opencode/opencode.json.
"""

from __future__ import annotations

import argparse
import os
import shlex
import sys
from pathlib import Path

from open_harness_common import openrouter_target, run_interactive


def _native_opencode() -> str:
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        candidate = Path(appdata) / "npm" / "opencode.cmd"
        if candidate.exists():
            return str(candidate)
    return "opencode"


def _delegate_native(argv: list[str]) -> int:
    cmd = [_native_opencode(), *argv]
    return run_interactive(cmd, os.environ.copy())


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--openrouter", action="store_true")
    parser.add_argument("--model", default="")
    parser.add_argument("--dry-run", action="store_true")
    args, passthrough = parser.parse_known_args()

    if not args.openrouter:
        return _delegate_native(sys.argv[1:])

    try:
        target = openrouter_target()
    except Exception as exc:
        print(f"[opencode] {exc}", file=sys.stderr)
        return 1

    model = args.model.strip() or target.model
    model_arg = f"openrouter/{model}"
    cmd = [_native_opencode(), "-m", model_arg, *passthrough]

    env = os.environ.copy()
    env["OPENROUTER_API_KEY"] = target.env_key_value
    env.pop("OPENAI_BASE_URL", None)

    print(f"[opencode] provider={target.provider_name} base_url={target.base_url} model={model_arg}")
    print("[opencode] env_key=OPENROUTER_API_KEY")
    print(f"[opencode] cmd={' '.join(shlex.quote(c) for c in cmd)}")

    if args.dry_run:
        return 0

    return run_interactive(cmd, env)


if __name__ == "__main__":
    raise SystemExit(main())
