"""Tests for skill.py guardrails: cost cap, idempotency, concurrency cap, AMD blocked."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models import GpuProvisionResult, HardwareTier, InstanceInfo, Provider


def run(coro):
    return asyncio.run(coro)


def _make_hardware(price_per_hour: float = 1.0, vram_gb: int = 16) -> HardwareTier:
    return HardwareTier(
        slug="nvidia-t4-x1",
        display_name="T4",
        vram_gb=vram_gb,
        price_per_hour=price_per_hour,
        provider=Provider.HUGGINGFACE,
    )


def _make_instance(name: str = "test-instance", status: str = "running") -> InstanceInfo:
    return InstanceInfo(
        id=name,
        name=name,
        provider=Provider.HUGGINGFACE,
        hardware_slug="nvidia-t4-x1",
        model_repo_id="google/gemma-2-2b-it",
        status=status,
        endpoint_url="https://example.modal.run",
    )


# ── Cost cap ──────────────────────────────────────────────────────────────────

class TestCostCap:
    def _run_with_settings(self, price: float, hours: int, limit: float) -> GpuProvisionResult:
        from skill import run_skill

        mock_hw = _make_hardware(price_per_hour=price)
        mock_model = MagicMock()
        mock_model.repo_id = "google/gemma-2-2b-it"

        with patch("skill.settings") as mock_settings, \
             patch("skill._resolve_hardware", new=AsyncMock(return_value=mock_hw)), \
             patch("skill._resolve_model", return_value=mock_model), \
             patch("skill.PROVIDER_MAP") as mock_map:

            mock_settings.max_spend_per_instance_usd = limit
            mock_settings.max_concurrent_instances = 10
            mock_settings.max_deployment_hours = 8
            mock_settings.uptime_report_interval_minutes = 30
            mock_settings.stuck_pending_minutes = 15
            mock_settings.watchdog_check_interval_minutes = 5
            mock_settings.openrouter_api_key = ""

            provider_inst = AsyncMock()
            provider_inst.list_instances = AsyncMock(return_value=[])
            mock_map.__getitem__ = MagicMock(return_value=lambda: provider_inst)

            return run(run_skill(
                provider="huggingface",
                hardware_slug="nvidia-t4-x1",
                model_repo_id="google/gemma-2-2b-it",
                instance_name="test-instance",
                max_deployment_hours=hours,
            ))

    def test_cost_below_limit_proceeds(self):
        result = self._run_with_settings(price=1.0, hours=4, limit=5.0)
        # Should not be blocked by cost cap (4 * 1.0 = $4 < $5)
        assert "cost check failed" not in result.message.lower()

    def test_cost_at_limit_blocked(self):
        result = self._run_with_settings(price=1.0, hours=6, limit=5.0)
        assert result.success is False
        assert "cost check failed" in result.message.lower()
        assert "6.00" in result.message

    def test_cost_exceeds_limit_blocked(self):
        result = self._run_with_settings(price=4.0, hours=8, limit=5.0)
        assert result.success is False
        assert "cost check failed" in result.message.lower()


# ── Idempotency ───────────────────────────────────────────────────────────────

class TestIdempotency:
    def test_returns_existing_active_instance(self):
        from skill import run_skill

        existing = _make_instance(name="my-gpu", status="running")
        mock_hw = _make_hardware()
        mock_model = MagicMock()
        mock_model.repo_id = "google/gemma-2-2b-it"

        with patch("skill.settings") as mock_settings, \
             patch("skill._resolve_hardware", new=AsyncMock(return_value=mock_hw)), \
             patch("skill._resolve_model", return_value=mock_model), \
             patch("skill.PROVIDER_MAP") as mock_map:

            mock_settings.max_spend_per_instance_usd = 100.0
            mock_settings.max_concurrent_instances = 10
            mock_settings.max_deployment_hours = 8
            mock_settings.uptime_report_interval_minutes = 30
            mock_settings.stuck_pending_minutes = 15
            mock_settings.watchdog_check_interval_minutes = 5

            provider_inst = AsyncMock()
            provider_inst.list_instances = AsyncMock(return_value=[existing])
            mock_map.__getitem__ = MagicMock(return_value=lambda: provider_inst)

            result = run(run_skill(
                provider="huggingface",
                hardware_slug="nvidia-t4-x1",
                model_repo_id="google/gemma-2-2b-it",
                instance_name="my-gpu",
            ))

        assert result.success is True
        assert result.instance is not None
        assert result.instance.name == "my-gpu"
        assert "existing" in result.message.lower()
        provider_inst.create_instance.assert_not_called()


# ── Concurrency cap ───────────────────────────────────────────────────────────

class TestConcurrencyCap:
    def test_blocks_when_cap_reached(self):
        from skill import run_skill

        live = [_make_instance(f"inst-{i}", "running") for i in range(2)]
        mock_hw = _make_hardware()
        mock_model = MagicMock()
        mock_model.repo_id = "google/gemma-2-2b-it"

        with patch("skill.settings") as mock_settings, \
             patch("skill._resolve_hardware", new=AsyncMock(return_value=mock_hw)), \
             patch("skill._resolve_model", return_value=mock_model), \
             patch("skill.PROVIDER_MAP") as mock_map:

            mock_settings.max_spend_per_instance_usd = 100.0
            mock_settings.max_concurrent_instances = 2
            mock_settings.max_deployment_hours = 8
            mock_settings.uptime_report_interval_minutes = 30
            mock_settings.stuck_pending_minutes = 15
            mock_settings.watchdog_check_interval_minutes = 5

            provider_inst = AsyncMock()
            provider_inst.list_instances = AsyncMock(return_value=live)
            mock_map.__getitem__ = MagicMock(return_value=lambda: provider_inst)

            result = run(run_skill(
                provider="huggingface",
                hardware_slug="nvidia-t4-x1",
                model_repo_id="google/gemma-2-2b-it",
                instance_name="new-inst",
            ))

        assert result.success is False
        assert "concurrency cap" in result.message.lower()
        assert "2/2" in result.message


# ── AMD blocked ───────────────────────────────────────────────────────────────

class TestAmdBlocked:
    def test_amd_returns_clear_blocked_message(self):
        from skill import run_skill

        result = run(run_skill(
            provider="amd",
            hardware_slug="mi300x",
            model_repo_id="Qwen/Qwen3-8B",
            instance_name="amd-test",
        ))

        assert result.success is False
        assert "amd" in result.message.lower() or "mi300x" in result.message.lower()
        assert "blocked" in result.message.lower()


# ── OpenRouter explicit selection ─────────────────────────────────────────────

class TestOpenRouterExplicit:
    def test_openrouter_direct_selection_returns_fallback(self):
        from skill import run_skill

        with patch("skill.settings") as mock_settings:
            mock_settings.openrouter_api_key = "sk-test"
            mock_settings.openrouter_model = "openrouter/auto"
            mock_settings.openrouter_base_url = "https://openrouter.ai/api/v1"

            result = run(run_skill(
                provider="openrouter",
                hardware_slug="any",
                model_repo_id="any/model",
                instance_name="test-or",
            ))

        assert result.fallback_activated is True
        assert result.instance is not None
        assert result.instance.provider == Provider.OPENROUTER
