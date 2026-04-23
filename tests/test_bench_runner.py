from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
BENCH_DIR = REPO_ROOT / ".bench"


def _load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module {module_name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_run_named_suite_supports_task_subset_and_run_label(tmp_path, monkeypatch):
    hb = _load_module("harness_benchmark", BENCH_DIR / "harness_benchmark.py")
    runner = _load_module("run_named_suite_test", BENCH_DIR / "run_named_suite.py")

    suite_path = tmp_path / "fake_suite.py"
    suite_path.write_text(
        "\n".join(
            [
                "TASKS = [",
                "    {'id': 'task_a', 'title': 'Task A', 'difficulty_0_100': 100},",
                "    {'id': 'task_b', 'title': 'Task B', 'difficulty_0_100': 100},",
                "]",
                "def build_prompt(task):",
                "    return f\"prompt:{task['id']}\"",
            ]
        ),
        encoding="utf-8",
    )

    captured_timeouts: list[int | None] = []

    def _fake_run_harness(harness, prompt, codex_result_file, timeout_s=None):
        captured_timeouts.append(timeout_s)
        return {
            "stdout": "PYTHON_START\nprint('ok')\nPYTHON_END",
            "stderr": "",
            "exit_code": 0,
            "duration_s": 1.25,
        }

    monkeypatch.setattr(runner, "_suite_module_path", lambda suite_id: suite_path)
    monkeypatch.setattr(runner.hb, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(runner.hb, "CODEX_MODEL", "gpt-oss-120b")
    monkeypatch.setattr(runner.hb, "CODEX_CLI", str(REPO_ROOT / "codexopen.cmd"))
    monkeypatch.setattr(runner.hb, "run_harness", _fake_run_harness)
    monkeypatch.setattr(runner, "_evaluate_code_with_timeout", lambda *args, **kwargs: (True, []))

    result = runner._run_suite(
        "extreme100",
        "codex",
        timeout_s=123,
        eval_timeout_s=45,
        task_ids=["task_b"],
        run_label="smoke10",
    )

    assert captured_timeouts == [123]
    assert "gemma4" not in result["run_dir"]
    assert "gpt-oss-120b" in result["run_dir"]
    assert "extreme100-smoke10" in result["run_dir"]

    payload = json.loads(Path(result["results_path"]).read_text(encoding="utf-8"))
    assert payload["config"]["run_label"] == "smoke10"
    assert payload["config"]["task_ids"] == ["task_b"]
    assert payload["config"]["selected_task_count"] == 1
    assert payload["config"]["suite_task_count"] == 2
    assert payload["config"]["actual_model_id"] == "gpt-oss-120b"
    assert payload["results"][0]["task_id"] == "task_b"


def test_select_tasks_rejects_unknown_task_id():
    _load_module("harness_benchmark", BENCH_DIR / "harness_benchmark.py")
    runner = _load_module("run_named_suite_validation", BENCH_DIR / "run_named_suite.py")
    tasks = [{"id": "known"}]

    with pytest.raises(ValueError, match="Unknown task IDs"):
        runner._select_tasks(tasks, ["missing"])
