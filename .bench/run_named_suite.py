#!/usr/bin/env python3
import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

import harness_benchmark as hb


Task = Dict[str, Any]
DEFAULT_EVAL_TIMEOUT_S = int(os.environ.get("BENCH_EVAL_TIMEOUT_S", "20"))


def _parse_csv(raw: str) -> List[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _sanitize_token(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-") or "run"


def _model_for_harness(harness: str) -> str:
    return {
        "qwen": hb.QWEN_MODEL,
        "opencode": hb.OPENCODE_MODEL,
        "codex": hb.CODEX_MODEL,
        "claude": hb.CLAUDE_MODEL,
        "goose": hb.GOOSE_MODEL,
    }[harness]


def _cli_for_harness(harness: str) -> str:
    return {
        "qwen": hb.QWEN_CLI,
        "opencode": hb.OPENCODE_CLI,
        "codex": hb.CODEX_CLI,
        "claude": hb.CLAUDE_CLI,
        "goose": hb.GOOSE_CLI,
    }[harness]


def _effective_base_url(harness: str) -> str:
    return hb.ANTHROPIC_BASE_URL if harness == "claude" else hb.OPENAI_BASE_URL


def _load_module(module_path: Path):
    spec = importlib.util.spec_from_file_location(module_path.stem, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _suite_module_path(suite_id: str) -> Path:
    mapping = {
        "medium60": Path(hb.__file__).resolve(),
        "hard80": (Path(hb.__file__).resolve().parent / "harness_benchmark_hard_opencode.py"),
        "hard90": (Path(hb.__file__).resolve().parent / "harness_benchmark_hard90_opencode.py"),
        "hard90_v2": (Path(hb.__file__).resolve().parent / "harness_benchmark_hard90_v2.py"),
        "extreme100": (Path(hb.__file__).resolve().parent / "harness_benchmark_extreme100.py"),
    }
    if suite_id not in mapping:
        raise ValueError(f"Unknown suite_id={suite_id}")
    return mapping[suite_id]


def _evaluate_code_with_timeout(module_path: Path, task_id: str, code: str, eval_timeout_s: int) -> Tuple[bool, List[str]]:
    helper = r"""
import importlib.util
import json
import sys

module_path = sys.argv[1]
task_id = sys.argv[2]
code = sys.stdin.read()

spec = importlib.util.spec_from_file_location("bench_suite_module", module_path)
if spec is None or spec.loader is None:
    print(json.dumps({"passed": False, "errors": [f"Could not load module: {module_path}"]}))
    raise SystemExit(0)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

tasks = getattr(module, "TASKS")
evaluate_code = getattr(module, "evaluate_code")
task = None
for t in tasks:
    if t.get("id") == task_id:
        task = t
        break

if task is None:
    print(json.dumps({"passed": False, "errors": [f"Unknown task_id: {task_id}"]}))
    raise SystemExit(0)

passed, errors = evaluate_code(task, code)
if not isinstance(errors, list):
    errors = [str(errors)]
print(json.dumps({"passed": bool(passed), "errors": errors}))
"""
    cmd = [sys.executable, "-c", helper, str(module_path), task_id]
    try:
        proc = subprocess.run(
            cmd,
            input=code,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=eval_timeout_s,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return False, [f"Evaluation timeout after {eval_timeout_s}s."]

    if proc.returncode != 0:
        err = (proc.stderr or "").strip()
        if not err:
            err = "no stderr output"
        return False, [f"Evaluation subprocess failed (exit={proc.returncode}): {err[:500]}"]

    lines = [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]
    for ln in reversed(lines):
        try:
            payload = json.loads(ln)
        except Exception:
            continue
        if isinstance(payload, dict):
            passed = bool(payload.get("passed", False))
            errors = payload.get("errors", [])
            if not isinstance(errors, list):
                errors = [str(errors)]
            return passed, [str(e) for e in errors]
    return False, ["Evaluation subprocess produced no parseable JSON result."]


def _select_tasks(tasks: List[Task], requested_task_ids: List[str] | None) -> List[Task]:
    if not requested_task_ids:
        return tasks
    wanted = set(requested_task_ids)
    selected = [task for task in tasks if task.get("id") in wanted]
    found = {task.get("id") for task in selected}
    missing = [task_id for task_id in requested_task_ids if task_id not in found]
    if missing:
        raise ValueError(f"Unknown task IDs for suite: {', '.join(missing)}")
    order = {task_id: idx for idx, task_id in enumerate(requested_task_ids)}
    return sorted(selected, key=lambda task: order[task["id"]])


def _run_suite(
    suite_id: str,
    harness: str,
    timeout_s: int = 600,
    eval_timeout_s: int = DEFAULT_EVAL_TIMEOUT_S,
    task_ids: List[str] | None = None,
    run_label: str = "",
) -> Dict[str, Any]:
    module_path = _suite_module_path(suite_id)
    module = _load_module(module_path)

    all_tasks: List[Task] = getattr(module, "TASKS")
    build_prompt: Callable[[Task], str] = getattr(module, "build_prompt")
    tasks = _select_tasks(all_tasks, task_ids)
    model_id = _model_for_harness(harness)
    model_token = _sanitize_token(model_id)
    label_token = _sanitize_token(run_label) if run_label else ""
    suite_token = _sanitize_token(f"{suite_id}-{label_token}") if label_token else _sanitize_token(suite_id)

    run_ts = int(time.time())
    run_dir = hb.RESULTS_DIR / f"run-{run_ts}-{harness}-{model_token}-{suite_token}"
    run_dir.mkdir(parents=True, exist_ok=True)

    results: List[Dict[str, Any]] = []
    for idx, task in enumerate(tasks, start=1):
        prompt = build_prompt(task)
        codex_result_file = run_dir / "raw" / harness / f"{task['id']}.codex_last.txt"
        run_info = hb.run_harness(harness, prompt, codex_result_file, timeout_s=timeout_s)
        response_text = run_info.get("response_text", "")
        code = hb.extract_code(response_text)
        passed, errors = _evaluate_code_with_timeout(module_path, task["id"], code, eval_timeout_s)

        hb.save_text(run_dir / "raw" / harness / f"{task['id']}.stdout.txt", run_info["stdout"])
        hb.save_text(run_dir / "raw" / harness / f"{task['id']}.stderr.txt", run_info["stderr"])
        hb.save_text(run_dir / "parsed" / harness / f"{task['id']}.response.txt", response_text)
        hb.save_text(run_dir / "parsed" / harness / f"{task['id']}.code.py", code)

        rec = {
            "id": f"{harness}_{task['id']}",
            "harness": harness,
            "suite_id": suite_id,
            "task_id": task["id"],
            "task_title": task.get("title", task["id"]),
            "difficulty_0_100": task.get("difficulty_0_100"),
            "exit_code": run_info["exit_code"],
            "duration_s": run_info["duration_s"],
            "passed": passed,
            "errors": errors,
        }
        results.append(rec)
        status = "PASS" if passed else "FAIL"
        print(
            f"[{harness}] {idx}/{len(tasks)} {suite_id}:{task['id']}: {status} "
            f"(exit={run_info['exit_code']}, {run_info['duration_s']}s)"
        )
        if errors:
            for err in errors[:3]:
                print(f"  - {err}")

    passes = sum(1 for r in results if r["passed"])
    summary = {
        "by_harness": {harness: {"passes": passes, "total": len(results)}},
        "overall_passes": passes,
        "overall_total": len(results),
    }
    payload = {
        "config": {
            "openai_base_url": hb.OPENAI_BASE_URL,
            "anthropic_base_url": hb.ANTHROPIC_BASE_URL,
            "effective_base_url": _effective_base_url(harness),
            "harness": harness,
            "suite_id": suite_id,
            "run_label": run_label,
            "task_ids": [task["id"] for task in tasks],
            "suite_task_count": len(all_tasks),
            "selected_task_count": len(tasks),
            "actual_model_id": model_id,
            "actual_cli": _cli_for_harness(harness),
            "opencode_model": hb.OPENCODE_MODEL,
            "qwen_model": hb.QWEN_MODEL,
            "codex_model": hb.CODEX_MODEL,
            "claude_model": hb.CLAUDE_MODEL,
            "timeout_s": timeout_s,
            "eval_timeout_s": eval_timeout_s,
            "module_path": str(module_path),
        },
        "results": results,
        "summary": summary,
    }
    hb.save_text(run_dir / "results.json", json.dumps(payload, indent=2))
    print(f"Summary {suite_id}: {passes}/{len(results)}")
    print(f"Artifacts: {run_dir}")
    return {
        "suite_id": suite_id,
        "run_label": run_label,
        "task_ids": [task["id"] for task in tasks],
        "run_dir": str(run_dir),
        "results_path": str(run_dir / "results.json"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one or more named benchmark suites for a single harness.")
    parser.add_argument("--harness", required=True, choices=["qwen", "opencode", "codex", "claude", "goose"])
    parser.add_argument("--suites", required=True, help="Comma-separated suite IDs (e.g., medium60,hard80,hard90).")
    parser.add_argument("--task-ids", default="", help="Optional comma-separated task IDs to run within each suite.")
    parser.add_argument("--run-label", default="", help="Optional label appended to artifact names and ledger entries.")
    parser.add_argument("--timeout-s", type=int, default=600)
    parser.add_argument("--eval-timeout-s", type=int, default=DEFAULT_EVAL_TIMEOUT_S)
    parser.add_argument("--ledger", default="", help="Optional path to write a JSON run ledger.")
    args = parser.parse_args()

    suites = _parse_csv(args.suites)
    task_ids = _parse_csv(args.task_ids)
    outputs = []
    for suite_id in suites:
        outputs.append(
            _run_suite(
                suite_id,
                args.harness,
                args.timeout_s,
                args.eval_timeout_s,
                task_ids=task_ids,
                run_label=args.run_label,
            )
        )

    if args.ledger:
        ledger_path = Path(args.ledger)
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        ledger_payload = {
            "harness": args.harness,
            "suites": suites,
            "task_ids": task_ids,
            "run_label": args.run_label,
            "runs": outputs,
        }
        ledger_path.write_text(json.dumps(ledger_payload, indent=2), encoding="utf-8")
        print(f"Ledger: {ledger_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
