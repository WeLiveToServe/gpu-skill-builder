#!/usr/bin/env python3
"""
opencode wrapper:
- With --openrouter/--activegpu: launch OpenCode with injected provider model settings.
- Without those flags: pass through to the native opencode CLI unchanged.
"""

from __future__ import annotations

import argparse
import os
import shlex
import sys
from pathlib import Path

from open_harness_common import resolve_target_sync, run_interactive


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


def _provider_model(provider: str, model: str) -> str:
    if provider == "openrouter":
        # opencode built-in openrouter provider: prefix with "openrouter/"
        return f"openrouter/{model}"
    # GPU endpoint: openai-compat provider
    return f"openai/{model}"


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--openrouter", action="store_true")
    parser.add_argument("--activegpu", action="store_true")
    parser.add_argument("--model", default="")
    parser.add_argument("--dry-run", action="store_true")
    args, passthrough = parser.parse_known_args()

    if not args.openrouter and not args.activegpu:
        return _delegate_native(sys.argv[1:])
    if args.openrouter and args.activegpu:
        print("[opencode] Choose only one of --openrouter or --activegpu.", file=sys.stderr)
        return 1

    try:
        target = resolve_target_sync(args.openrouter, args.activegpu)
    except Exception as exc:
        print(f"[opencode] {exc}", file=sys.stderr)
        return 1

    model = args.model.strip() or target.model
    model_arg = _provider_model(target.provider_name, model)
    cmd = [_native_opencode(), "-m", model_arg, *passthrough]

    env = os.environ.copy()
    env[target.env_key_name] = target.env_key_value
    if target.provider_name == "openrouter":
        # opencode's built-in openrouter provider reads OPENROUTER_API_KEY.
        # Do NOT set OPENAI_API_KEY to avoid colliding with the real key in .env.
        env["OPENROUTER_API_KEY"] = target.env_key_value
        env.pop("OPENAI_BASE_URL", None)
    else:
        # GPU endpoint: inject as OpenAI-compat provider.
        env["OPENAI_API_KEY"] = target.env_key_value
        env["OPENAI_BASE_URL"] = target.base_url

    active_key = "OPENROUTER_API_KEY" if target.provider_name == "openrouter" else "OPENAI_API_KEY"
    print(f"[opencode] provider={target.provider_name} base_url={target.base_url} model={model_arg}")
    print(f"[opencode] env_key={active_key}")
    print(f"[opencode] cmd={' '.join(shlex.quote(c) for c in cmd)}")

    if args.dry_run:
        return 0

    return run_interactive(cmd, env)


if __name__ == "__main__":
    raise SystemExit(main())
