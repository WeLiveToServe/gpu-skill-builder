#!/usr/bin/env python3
import argparse
import importlib.util
import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

import harness_benchmark as hb


Task = Dict[str, Any]


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


def _run_suite(suite_id: str, harness: str, timeout_s: int = 600) -> Dict[str, Any]:
    module_path = _suite_module_path(suite_id)
    module = _load_module(module_path)

    tasks: List[Task] = getattr(module, "TASKS")
    build_prompt: Callable[[Task], str] = getattr(module, "build_prompt")
    evaluate_code: Callable[[Task, str], Tuple[bool, List[str]]] = getattr(module, "evaluate_code")

    run_ts = int(time.time())
    run_dir = hb.RESULTS_DIR / f"run-{run_ts}-{harness}-gemma4-{suite_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    results: List[Dict[str, Any]] = []
    for idx, task in enumerate(tasks, start=1):
        prompt = build_prompt(task)
        codex_result_file = run_dir / "raw" / harness / f"{task['id']}.codex_last.txt"
        run_info = hb.run_harness(harness, prompt, codex_result_file)
        response_text = run_info.get("response_text", "")
        code = hb.extract_code(response_text)
        passed, errors = evaluate_code(task, code)

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
            "harness": harness,
            "suite_id": suite_id,
            "opencode_model": hb.OPENCODE_MODEL,
            "qwen_model": hb.QWEN_MODEL,
            "codex_model": hb.CODEX_MODEL,
            "claude_model": hb.CLAUDE_MODEL,
            "timeout_s": timeout_s,
            "module_path": str(module_path),
        },
        "results": results,
        "summary": summary,
    }
    hb.save_text(run_dir / "results.json", json.dumps(payload, indent=2))
    print(f"Summary {suite_id}: {passes}/{len(results)}")
    print(f"Artifacts: {run_dir}")
    return {"suite_id": suite_id, "run_dir": str(run_dir), "results_path": str(run_dir / "results.json")}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one or more named benchmark suites for a single harness.")
    parser.add_argument("--harness", required=True, choices=["qwen", "opencode", "codex", "claude", "goose"])
    parser.add_argument("--suites", required=True, help="Comma-separated suite IDs (e.g., medium60,hard80,hard90).")
    parser.add_argument("--timeout-s", type=int, default=600)
    parser.add_argument("--ledger", default="", help="Optional path to write a JSON run ledger.")
    args = parser.parse_args()

    suites = [s.strip() for s in args.suites.split(",") if s.strip()]
    outputs = []
    for suite_id in suites:
        outputs.append(_run_suite(suite_id, args.harness, args.timeout_s))

    if args.ledger:
        ledger_path = Path(args.ledger)
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        ledger_payload = {"harness": args.harness, "suites": suites, "runs": outputs}
        ledger_path.write_text(json.dumps(ledger_payload, indent=2), encoding="utf-8")
        print(f"Ledger: {ledger_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
