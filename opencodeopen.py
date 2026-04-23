#!/usr/bin/env python3
"""
opencode wrapper:
- With --openrouter: launch OpenCode routed to OpenRouter.
- Without flags: launch OpenRouter mode by default for normal run usage.
- Pass through unchanged for native management subcommands.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
from pathlib import Path

from open_harness_common import openrouter_target, resolve_locked_model, run_interactive


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


def _provider_model_id(model_id: str) -> str:
    if model_id.startswith("openrouter/"):
        return model_id[len("openrouter/"):]
    return model_id


def _display_name(model_id: str) -> str:
    return _provider_model_id(model_id).replace("/", " / ")


def _family_for_model(model_id: str) -> str:
    lowered = _provider_model_id(model_id).lower()
    if "qwen" in lowered:
        return "qwen"
    if "claude" in lowered:
        return "claude"
    if "gpt" in lowered or "o1" in lowered or "o3" in lowered:
        return "openai"
    return "generic"


def _openrouter_config_content(target_base_url: str, model_id: str, api_key: str) -> str:
    # Force an in-memory OpenCode config for OpenRouter-only execution so stale
    # local/global provider files cannot drop auth headers or reroute models.
    provider_model_id = _provider_model_id(model_id)
    options = {
        "baseURL": target_base_url,
        "apiKey": api_key,
    }
    if "openrouter.ai" in target_base_url:
        options["headers"] = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://opencode.ai/",
            "X-Title": "opencode",
        }
    config = {
        "$schema": "https://opencode.ai/config.json",
        "model": model_id,
        "small_model": model_id,
        "enabled_providers": ["openrouter"],
        "provider": {
            "openrouter": {
                "name": "OpenRouter",
                "npm": "@ai-sdk/openai-compatible",
                "options": options,
                "models": {
                    provider_model_id: {
                        "id": provider_model_id,
                        "name": _display_name(model_id),
                        "family": _family_for_model(model_id),
                        "attachment": True,
                        "reasoning": True,
                        "temperature": True,
                        "tool_call": True,
                        "limit": {
                            "context": 131072,
                            "output": 8192,
                        },
                    }
                },
            }
        },
    }
    return json.dumps(config, separators=(",", ":"))


def _ensure_isolated_xdg_dirs() -> tuple[str, str, str, str]:
    root = Path.home() / ".opencode-openrouter"
    data_home = root / "data"
    config_home = root / "config"
    cache_home = root / "cache"
    state_home = root / "state"
    for p in (data_home, config_home, cache_home, state_home):
        p.mkdir(parents=True, exist_ok=True)
    return (str(data_home), str(config_home), str(cache_home), str(state_home))


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--openrouter", action="store_true")
    parser.add_argument("--model", default="")
    parser.add_argument("--dry-run", action="store_true")
    args, passthrough = parser.parse_known_args()

    if not args.openrouter:
        native_passthrough = {
            "acp",
            "agent",
            "attach",
            "completion",
            "db",
            "debug",
            "export",
            "github",
            "import",
            "mcp",
            "models",
            "plugin",
            "plugins",
            "pr",
            "providers",
            "auth",
            "serve",
            "session",
            "stats",
            "uninstall",
            "upgrade",
            "web",
            "--help",
            "-h",
            "--version",
            "-v",
        }
        if passthrough and passthrough[0] in native_passthrough:
            return _delegate_native(sys.argv[1:])
        args.openrouter = True

    try:
        target = openrouter_target()
        model = resolve_locked_model(args.model)
    except Exception as exc:
        print(f"[opencode] {exc}", file=sys.stderr)
        return 1

    model_arg = f"openrouter/{model}"
    cmd = [_native_opencode(), "-m", model_arg, *passthrough]

    env = os.environ.copy()
    xdg_data_home, xdg_config_home, xdg_cache_home, xdg_state_home = _ensure_isolated_xdg_dirs()
    env["XDG_DATA_HOME"] = xdg_data_home
    env["XDG_CONFIG_HOME"] = xdg_config_home
    env["XDG_CACHE_HOME"] = xdg_cache_home
    env["XDG_STATE_HOME"] = xdg_state_home
    env["OPENROUTER_API_KEY"] = target.env_key_value
    env["OPENAI_API_KEY"] = target.env_key_value
    env["OPENCODE_MODEL"] = model_arg
    env["OPENCODE_CONFIG_CONTENT"] = _openrouter_config_content(
        target_base_url=target.base_url,
        model_id=model_arg,
        api_key=target.env_key_value,
    )
    env.pop("OPENAI_BASE_URL", None)

    print(f"[opencode] provider={target.provider_name} base_url={target.base_url} model={model_arg}", file=sys.stderr)
    print("[opencode] env_key=OPENROUTER_API_KEY", file=sys.stderr)
    print("[opencode] mode=forced-openrouter-config", file=sys.stderr)
    print(f"[opencode] xdg_root={str(Path.home() / '.opencode-openrouter')}", file=sys.stderr)
    print(f"[opencode] cmd={' '.join(shlex.quote(c) for c in cmd)}", file=sys.stderr)

    if args.dry_run:
        return 0

    return run_interactive(cmd, env)


if __name__ == "__main__":
    raise SystemExit(main())
