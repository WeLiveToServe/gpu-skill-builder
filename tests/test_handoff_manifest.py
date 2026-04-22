import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from endpoint_probe import ProbeClassification
from models import GpuProvisionResult, HardwareTier, InstanceInfo, Provider
from skill import ensure_active_endpoint, run_skill


def run(coro):
    return asyncio.run(coro)


def _hardware() -> HardwareTier:
    return HardwareTier(
        slug="gpu-h200x1-141gb",
        display_name="DigitalOcean H200 x1",
        vram_gb=141,
        price_per_hour=4.54,
        provider=Provider.DIGITALOCEAN,
        region="nyc1",
    )


def _instance() -> InstanceInfo:
    return InstanceInfo(
        id="droplet-1",
        name="gpu-skill-instance",
        provider=Provider.DIGITALOCEAN,
        hardware_slug="gpu-h200x1-141gb",
        model_repo_id="openai/gpt-oss-120b",
        status="running",
        endpoint_url="http://1.2.3.4:8000",
        region="nyc1",
    )


class TestHandoffManifest:
    def test_run_skill_returns_non_secret_handoff_manifest(self):
        created = _instance()
        mock_model = MagicMock()
        mock_model.repo_id = "openai/gpt-oss-120b"

        with patch("skill.settings") as mock_settings, \
             patch("skill._resolve_hardware", new=AsyncMock(return_value=_hardware())), \
             patch("skill._resolve_model", return_value=mock_model), \
             patch("skill.PROVIDER_MAP") as mock_map, \
             patch("scheduler.schedule_ttl"), \
             patch("scheduler.schedule_uptime_report"), \
             patch("scheduler.schedule_stuck_watchdog"):

            mock_settings.max_spend_per_instance_usd = 1000.0
            mock_settings.max_concurrent_instances = 10
            mock_settings.max_deployment_hours = 8
            mock_settings.uptime_report_interval_minutes = 30
            mock_settings.stuck_pending_minutes = 15
            mock_settings.watchdog_check_interval_minutes = 5
            mock_settings.monitor_enabled = False

            provider_inst = AsyncMock()
            provider_inst.list_instances = AsyncMock(return_value=[])
            provider_inst.create_instance = AsyncMock(return_value=created)
            mock_map.__getitem__ = MagicMock(return_value=lambda: provider_inst)

            result = run(
                run_skill(
                    provider="digitalocean",
                    hardware_slug="gpu-h200x1-141gb",
                    model_repo_id="openai/gpt-oss-120b",
                )
            )

        assert result.success is True
        assert result.readiness_state == "provisioned-unverified"
        assert result.harness_handoff is not None
        assert result.harness_handoff.base_url == "http://1.2.3.4:8000/v1"
        assert result.harness_handoff.model_name == "gpt-oss-120b"
        assert result.harness_handoff.expected_env is not None
        assert result.harness_handoff.expected_env.base_url_key_name == "OPENAI_BASE_URL"
        assert "API_KEY" in result.harness_handoff.expected_env.api_key_key_name
        assert "hf_" not in result.harness_handoff.model_dump_json()

    def test_ensure_active_endpoint_upgrades_readiness_without_changing_boundary(self):
        starting = GpuProvisionResult(
            success=True,
            instance=_instance(),
            message="Instance created successfully.",
            readiness_state="provisioned-unverified",
        )

        with patch("skill.PROVIDER_MAP") as mock_map, \
             patch("skill.probe_openai_compatible_endpoint", new=AsyncMock()) as probe:
            provider_inst = AsyncMock()
            provider_inst.get_instance = AsyncMock(return_value=_instance())
            mock_map.__getitem__ = MagicMock(return_value=lambda: provider_inst)
            probe.return_value = MagicMock(classification=ProbeClassification.READY, detail="")

            result = run(ensure_active_endpoint(starting))

        assert result.success is True
        assert result.readiness_state == "verified-ready"
        assert result.harness_handoff is not None
        assert result.harness_handoff.readiness_state == "verified-ready"
