#!/usr/bin/env python3
"""
qwen wrapper:
- With --openrouter/--activegpu: launch Qwen CLI with OpenAI-compatible endpoint wiring.
- Without those flags: pass through to the native qwen CLI unchanged.
"""

from __future__ import annotations

import argparse
import os
import shlex
import sys
from pathlib import Path

from open_harness_common import resolve_target_sync, run_interactive


def _native_qwen() -> str:
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        candidate = Path(appdata) / "npm" / "qwen.cmd"
        if candidate.exists():
            return str(candidate)
    return "qwen"


def _delegate_native(argv: list[str]) -> int:
    cmd = [_native_qwen(), *argv]
    return run_interactive(cmd, os.environ.copy())


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--openrouter", action="store_true")
    parser.add_argument("--activegpu", action="store_true")
    parser.add_argument("--model", default="")
    parser.add_argument("--dry-run", action="store_true")
    args, passthrough = parser.parse_known_args()

    if not args.openrouter and not args.activegpu:
        native_passthrough = {"mcp", "extensions", "auth", "hooks", "hook", "channel", "--help", "-h", "--version", "-v"}
        if passthrough and passthrough[0] in native_passthrough:
            return _delegate_native(sys.argv[1:])
        args.openrouter = True
    if args.openrouter and args.activegpu:
        print("[qwen] Choose only one of --openrouter or --activegpu.", file=sys.stderr)
        return 1

    try:
        target = resolve_target_sync(args.openrouter, args.activegpu)
    except Exception as exc:
        print(f"[qwen] {exc}", file=sys.stderr)
        return 1

    model = args.model.strip() or target.model
    cmd = [
        _native_qwen(),
        "--auth-type",
        "openai",
        "--openai-api-key",
        target.env_key_value,
        "--openai-base-url",
        target.base_url,
        "--model",
        model,
        *passthrough,
    ]
    cmd_redacted = cmd.copy()
    try:
        key_idx = cmd_redacted.index("--openai-api-key")
        if key_idx + 1 < len(cmd_redacted):
            cmd_redacted[key_idx + 1] = "***REDACTED***"
    except ValueError:
        pass

    env = os.environ.copy()
    env[target.env_key_name] = target.env_key_value
    env["OPENAI_API_KEY"] = target.env_key_value
    env["OPENAI_BASE_URL"] = target.base_url
    # Avoid stale shell-level model var causing invalid model resolution in native qwen config.
    env["OPENROUTER_MODEL_ID"] = model

    print(f"[qwen] provider={target.provider_name} base_url={target.base_url} model={model}")
    print("[qwen] env_key=OPENAI_API_KEY")
    print(f"[qwen] cmd={' '.join(shlex.quote(c) for c in cmd_redacted)}")

    if args.dry_run:
        return 0

    return run_interactive(cmd, env)


if __name__ == "__main__":
    raise SystemExit(main())
