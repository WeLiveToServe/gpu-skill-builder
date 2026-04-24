from __future__ import annotations

import json

from open_harness_common import openrouter_target, resolve_locked_model
from opencodeopen import _opencode_model_arg, _openrouter_config_content


def test_openrouter_target_prefers_process_local_harness_overrides(monkeypatch):
    monkeypatch.setenv("HARNESS_OPENROUTER_BASE_URL", "http://127.0.0.1:18000/v1")
    monkeypatch.setenv("HARNESS_OPENROUTER_MODEL", "gpt-oss-120b")
    monkeypatch.setenv("HARNESS_OPENROUTER_API_KEY", "local-key")

    target = openrouter_target()

    assert target.base_url == "http://127.0.0.1:18000/v1"
    assert target.model == "gpt-oss-120b"
    assert target.env_key_value == "local-key"
    assert resolve_locked_model() == "gpt-oss-120b"


def test_opencode_config_supports_dynamic_local_gpu_model():
    payload = json.loads(
        _openrouter_config_content(
            "http://127.0.0.1:18000/v1",
            "openrouter/gpt-oss-120b",
            "bench-key",
        )
    )

    provider = payload["provider"]["openrouter"]
    assert payload["model"] == "openrouter/gpt-oss-120b"
    assert provider["options"]["baseURL"] == "http://127.0.0.1:18000/v1"
    assert provider["options"]["headers"]["Authorization"] == "Bearer bench-key"
    assert "gpt-oss-120b" in provider["models"]
    assert provider["models"]["gpt-oss-120b"]["tool_call"] is True


def test_opencode_model_arg_does_not_double_prefix_openrouter_auto():
    assert _opencode_model_arg("openrouter/auto") == "openrouter/auto"
    assert _opencode_model_arg("qwen/qwen3.6-plus") == "openrouter/qwen/qwen3.6-plus"
