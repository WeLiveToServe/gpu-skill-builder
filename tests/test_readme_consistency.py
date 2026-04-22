from pathlib import Path


ROOT_README = Path(__file__).resolve().parents[1] / "README.md"


def test_root_readme_lists_current_monitor_env_vars():
    text = ROOT_README.read_text(encoding="utf-8")
    expected = [
        "GPU_MONITOR_ENABLED",
        "GPU_MONITOR_INTERVAL_MINUTES",
        "GPU_MONITOR_RUNTIME_ALERT_MINUTES",
        "GPU_MONITOR_AUTO_STOP_MINUTES",
        "GPU_MONITOR_READINESS_POLL_SECONDS",
        "GPU_MONITOR_READINESS_TIMEOUT_MINUTES",
        "GPU_MONITOR_STALE_AFTER_MINUTES",
        "GPU_MONITOR_UNHEALTHY_AUTO_STOP_MINUTES",
    ]
    for env_var in expected:
        assert env_var in text


def test_root_readme_marks_production_grade_docs_as_draft():
    text = ROOT_README.read_text(encoding="utf-8").lower()
    assert "draft planning material" in text or "draft planning artifacts" in text


def test_root_readme_no_longer_claims_no_wait_for_ready_loop():
    text = ROOT_README.read_text(encoding="utf-8").lower()
    assert "no wait-for-ready loop exists yet" not in text
