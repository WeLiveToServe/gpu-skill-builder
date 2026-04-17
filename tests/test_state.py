"""Tests for state file read/write: atomicity, corruption handling, round-trips."""
import json
import sys
from pathlib import Path

import pytest


# ── do_bootstrap state ────────────────────────────────────────────────────────

class TestDoState:
    def test_round_trip(self, tmp_path, monkeypatch):
        import do_bootstrap
        monkeypatch.setattr(do_bootstrap, "STATE_FILE", tmp_path / ".do_state.json")

        state = {"do_ssh_key_id": 12345, "last_droplet": {"id": 99, "ip": "1.2.3.4"}}
        do_bootstrap._save_state(state)
        loaded = do_bootstrap._load_state()
        assert loaded == state

    def test_corrupted_file_returns_empty(self, tmp_path, monkeypatch):
        import do_bootstrap
        state_file = tmp_path / ".do_state.json"
        state_file.write_text("{this is not valid json")
        monkeypatch.setattr(do_bootstrap, "STATE_FILE", state_file)

        result = do_bootstrap._load_state()
        assert result == {}

    def test_missing_file_returns_empty(self, tmp_path, monkeypatch):
        import do_bootstrap
        monkeypatch.setattr(do_bootstrap, "STATE_FILE", tmp_path / "nonexistent.json")

        result = do_bootstrap._load_state()
        assert result == {}

    def test_atomic_write_uses_tmp_then_replaces(self, tmp_path, monkeypatch):
        import do_bootstrap
        state_file = tmp_path / ".do_state.json"
        monkeypatch.setattr(do_bootstrap, "STATE_FILE", state_file)

        do_bootstrap._save_state({"key": "value"})

        assert state_file.exists()
        # .tmp should be cleaned up after atomic replace
        assert not state_file.with_suffix(".tmp").exists()

    def test_second_save_overwrites_first(self, tmp_path, monkeypatch):
        import do_bootstrap
        monkeypatch.setattr(do_bootstrap, "STATE_FILE", tmp_path / ".do_state.json")

        do_bootstrap._save_state({"v": 1})
        do_bootstrap._save_state({"v": 2})
        assert do_bootstrap._load_state() == {"v": 2}


# ── modal_bootstrap state ─────────────────────────────────────────────────────

class TestModalState:
    def test_round_trip(self, tmp_path, monkeypatch):
        import modal_bootstrap
        monkeypatch.setattr(modal_bootstrap, "STATE_FILE", tmp_path / ".modal_state.json")

        state = {"apps": {"my-app": {"app_id": "ap-abc", "endpoint_url": "https://x.modal.run", "gpu": "H100", "model": "Qwen/Qwen3-8B", "status": "deployed", "app_name": "my-app"}}}
        modal_bootstrap._save_state(state)
        loaded = modal_bootstrap._load_state()
        assert loaded == state

    def test_corrupted_file_returns_empty(self, tmp_path, monkeypatch):
        import modal_bootstrap
        state_file = tmp_path / ".modal_state.json"
        state_file.write_text("<<<CORRUPTED>>>")
        monkeypatch.setattr(modal_bootstrap, "STATE_FILE", state_file)

        assert modal_bootstrap._load_state() == {}

    def test_missing_file_returns_empty(self, tmp_path, monkeypatch):
        import modal_bootstrap
        monkeypatch.setattr(modal_bootstrap, "STATE_FILE", tmp_path / "ghost.json")

        assert modal_bootstrap._load_state() == {}

    def test_atomic_write_no_leftover_tmp(self, tmp_path, monkeypatch):
        import modal_bootstrap
        state_file = tmp_path / ".modal_state.json"
        monkeypatch.setattr(modal_bootstrap, "STATE_FILE", state_file)

        modal_bootstrap._save_state({"apps": {}})

        assert state_file.exists()
        assert not state_file.with_suffix(".tmp").exists()
