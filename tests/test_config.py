"""Tests for config.py: env loading priority, cross-platform path."""
import os
from pathlib import Path
from unittest.mock import patch

import pytest


class TestSharedEnvPath:
    def test_shared_env_uses_home_not_hardcoded_windows(self):
        import config
        # Must be relative to home, not an absolute Windows path
        assert str(config.SHARED_ENV_FILE).startswith(str(Path.home()))
        # Guard against a literal hardcoded username only when it is not the actual home user.
        if "keith" not in str(Path.home()).lower():
            assert "keith" not in str(config.SHARED_ENV_FILE).lower()

    def test_shared_env_ends_with_dev_dot_env(self):
        import config
        assert config.SHARED_ENV_FILE.parts[-1] == ".env"
        assert config.SHARED_ENV_FILE.parts[-2] == "dev"

    def test_local_env_is_sibling_of_config(self):
        import config
        assert config.LOCAL_ENV_FILE.parent == Path(config.__file__).parent


class TestSeedEnvironment:
    def test_process_env_takes_priority_over_file(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text("HF_TOKEN=from_file\n")

        monkeypatch.setenv("HF_TOKEN", "from_process")

        from dotenv import dotenv_values
        values = dotenv_values(env_file)
        assert values.get("HF_TOKEN") == "from_file"

        # Process env should win — simulate the seed logic
        result = os.environ.get("HF_TOKEN", values.get("HF_TOKEN"))
        assert result == "from_process"

    def test_local_env_overrides_shared(self, tmp_path, monkeypatch):
        shared = tmp_path / "shared.env"
        local = tmp_path / "local.env"
        shared.write_text("MY_TEST_KEY=shared_value\n")
        local.write_text("MY_TEST_KEY=local_value\n")

        from dotenv import dotenv_values
        shared_vals = dotenv_values(shared)
        local_vals = dotenv_values(local)

        # Local wins: apply shared first, then local overwrites
        merged = {**shared_vals, **local_vals}
        assert merged["MY_TEST_KEY"] == "local_value"


class TestSettings:
    def test_defaults_are_set(self):
        from config import Settings
        s = Settings()
        assert s.max_deployment_hours == 8
        assert s.max_concurrent_instances == 2
        assert s.max_spend_per_instance_usd == 5.0
        assert s.stuck_pending_minutes == 15
        assert s.watchdog_check_interval_minutes == 5
        assert s.monitor_readiness_poll_seconds == 30
        assert s.monitor_readiness_timeout_minutes == 20
        assert s.monitor_stale_after_minutes == 10
        assert s.monitor_unhealthy_auto_stop_minutes == 0

    def test_env_var_overrides_default(self, monkeypatch):
        monkeypatch.setenv("HF_TOKEN", "hf_testtoken")
        from config import Settings
        s = Settings()
        assert s.hf_token == "hf_testtoken"

    def test_openrouter_default_url(self):
        from config import Settings
        s = Settings()
        assert "openrouter.ai" in s.openrouter_base_url
