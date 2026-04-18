#!/usr/bin/env python3
import json
import time
from typing import Any, Callable, Dict, List, Tuple

import harness_benchmark as hb


TaskChecker = Callable[[Dict[str, Any]], List[str]]


def check_sum_of_distances_in_tree(ns: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    fn = ns.get("sum_of_distances_in_tree")
    if not callable(fn):
        return ["Missing callable sum_of_distances_in_tree(n, edges)."]
    cases = [
        (6, [(0, 1), (0, 2), (2, 3), (2, 4), (2, 5)], [8, 12, 6, 10, 10, 10]),
        (1, [], [0]),
        (2, [(1, 0)], [1, 1]),
    ]
    for n, edges, expected in cases:
        try:
            got = fn(n, edges)
            if got != expected:
                errors.append(f"sum_of_distances_in_tree({n}, {edges}) -> {got}, expected {expected}")
        except Exception as exc:
            errors.append(f"Exception in sum_of_distances_in_tree case {n}: {exc}")
    return errors


def check_merge_stones(ns: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    fn = ns.get("merge_stones")
    if not callable(fn):
        return ["Missing callable merge_stones(stones, k)."]
    cases = [
        ([3, 2, 4, 1], 2, 20),
        ([3, 2, 4, 1], 3, -1),
        ([3, 5, 1, 2, 6], 3, 25),
        ([6, 4, 4, 6], 2, 40),
    ]
    for stones, k, expected in cases:
        try:
            got = fn(stones, k)
            if got != expected:
                errors.append(f"merge_stones({stones}, {k}) -> {got}, expected {expected}")
        except Exception as exc:
            errors.append(f"Exception in merge_stones case {stones}, k={k}: {exc}")
    return errors


def check_count_range_sum(ns: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    fn = ns.get("count_range_sum")
    if not callable(fn):
        return ["Missing callable count_range_sum(nums, lower, upper)."]
    cases = [
        ([-2, 5, -1], -2, 2, 3),
        ([0], 0, 0, 1),
        ([1, -1, 1], 0, 1, 5),
    ]
    for nums, lower, upper, expected in cases:
        try:
            got = fn(nums, lower, upper)
            if got != expected:
                errors.append(
                    f"count_range_sum({nums}, {lower}, {upper}) -> {got}, expected {expected}"
                )
        except Exception as exc:
            errors.append(f"Exception in count_range_sum case {nums}: {exc}")
    return errors


def check_critical_pseudo_critical(ns: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    fn = ns.get("find_critical_and_pseudo_critical_edges")
    if not callable(fn):
        return ["Missing callable find_critical_and_pseudo_critical_edges(n, edges)."]
    cases = [
        (
            5,
            [(0, 1, 1), (1, 2, 1), (2, 3, 2), (0, 3, 2), (0, 4, 3), (3, 4, 3), (1, 4, 6)],
            ([0, 1], [2, 3, 4, 5]),
        ),
        (
            4,
            [(0, 1, 1), (1, 2, 1), (2, 3, 1), (0, 3, 1)],
            ([], [0, 1, 2, 3]),
        ),
    ]
    for n, edges, expected in cases:
        try:
            got = fn(n, edges)
            if not isinstance(got, list) or len(got) != 2:
                errors.append(f"Expected [critical, pseudo] list, got {got}")
                continue
            crit = sorted(got[0])
            pseudo = sorted(got[1])
            exp_crit = sorted(expected[0])
            exp_pseudo = sorted(expected[1])
            if crit != exp_crit or pseudo != exp_pseudo:
                errors.append(
                    f"find_critical_and_pseudo_critical_edges(...) -> {[crit, pseudo]}, "
                    f"expected {[exp_crit, exp_pseudo]}"
                )
        except Exception as exc:
            errors.append(f"Exception in critical/pseudo case n={n}: {exc}")
    return errors


def check_min_stickers(ns: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    fn = ns.get("min_stickers")
    if not callable(fn):
        return ["Missing callable min_stickers(stickers, target)."]
    cases = [
        (["with", "example", "science"], "thehat", 3),
        (["notice", "possible"], "basicbasic", -1),
        (["a", "b", "ab"], "abb", 2),
        (["abc", "ab", "bc"], "aabbcc", 2),
    ]
    for stickers, target, expected in cases:
        try:
            got = fn(stickers, target)
            if got != expected:
                errors.append(f"min_stickers({stickers}, {target!r}) -> {got}, expected {expected}")
        except Exception as exc:
            errors.append(f"Exception in min_stickers case {target!r}: {exc}")
    return errors


TASKS: List[Dict[str, Any]] = [
    {
        "id": "hard90_sum_of_distances_tree",
        "title": "Sum of Distances in Tree",
        "difficulty_0_100": 90,
        "description": (
            "Implement: def sum_of_distances_in_tree(n: int, edges: list[tuple[int, int]]) -> list[int]. "
            "For each node i, return sum of distances from i to all nodes in the tree."
        ),
        "checker": check_sum_of_distances_in_tree,
    },
    {
        "id": "hard90_merge_stones",
        "title": "Minimum Cost to Merge Stones",
        "difficulty_0_100": 91,
        "description": (
            "Implement: def merge_stones(stones: list[int], k: int) -> int. "
            "Merge exactly k consecutive piles each move; return minimum total cost or -1 if impossible."
        ),
        "checker": check_merge_stones,
    },
    {
        "id": "hard90_count_range_sum",
        "title": "Count of Range Sum",
        "difficulty_0_100": 89,
        "description": (
            "Implement: def count_range_sum(nums: list[int], lower: int, upper: int) -> int. "
            "Count range sums S(i..j) with lower <= sum <= upper."
        ),
        "checker": check_count_range_sum,
    },
    {
        "id": "hard90_critical_pseudo_edges",
        "title": "Critical and Pseudo-Critical Edges in MST",
        "difficulty_0_100": 92,
        "description": (
            "Implement: def find_critical_and_pseudo_critical_edges("
            "n: int, edges: list[tuple[int, int, int]]) -> list[list[int]]. "
            "Edges are indexed by input order. Return [critical_indices, pseudo_critical_indices]."
        ),
        "checker": check_critical_pseudo_critical,
    },
    {
        "id": "hard90_min_stickers",
        "title": "Stickers to Spell Word",
        "difficulty_0_100": 90,
        "description": (
            "Implement: def min_stickers(stickers: list[str], target: str) -> int. "
            "Return minimum stickers needed to form target, or -1 if impossible."
        ),
        "checker": check_min_stickers,
    },
]


def build_prompt(task: Dict[str, Any]) -> str:
    return (
        "Solve this Python task. Output format is mandatory: "
        "PYTHON_START then valid Python source code then PYTHON_END. "
        "No prose. No markdown. "
        f"{task['description']}"
    )


def evaluate_code(task: Dict[str, Any], code: str) -> Tuple[bool, List[str]]:
    ns: Dict[str, Any] = {}
    try:
        exec(
            "from typing import *\n"
            "from collections import *\n"
            "from bisect import *\n"
            "import math\n"
            "import heapq\n",
            ns,
            ns,
        )
        exec(code, ns, ns)  # nosec - benchmark-only evaluation harness
    except Exception as exc:
        return False, [f"Code execution raised: {exc}"]
    checker: TaskChecker = task["checker"]
    errors = checker(ns)
    return len(errors) == 0, errors


def main() -> int:
    run_ts = int(time.time())
    run_dir = hb.RESULTS_DIR / f"run-{run_ts}-opencode-gemma4-hard90"
    run_dir.mkdir(parents=True, exist_ok=True)

    results: List[Dict[str, Any]] = []
    for idx, task in enumerate(TASKS, start=1):
        prompt = build_prompt(task)
        run_info = hb.run_opencode(prompt, timeout_s=480)
        response_text = run_info.get("response_text", "")
        code = hb.extract_code(response_text)
        passed, errors = evaluate_code(task, code)

        hb.save_text(run_dir / "raw" / "opencode" / f"{task['id']}.stdout.txt", run_info["stdout"])
        hb.save_text(run_dir / "raw" / "opencode" / f"{task['id']}.stderr.txt", run_info["stderr"])
        hb.save_text(run_dir / "parsed" / "opencode" / f"{task['id']}.response.txt", response_text)
        hb.save_text(run_dir / "parsed" / "opencode" / f"{task['id']}.code.py", code)

        rec = {
            "id": f"opencode_{task['id']}",
            "harness": "opencode",
            "task_id": task["id"],
            "task_title": task["title"],
            "difficulty_0_100": task["difficulty_0_100"],
            "exit_code": run_info["exit_code"],
            "duration_s": run_info["duration_s"],
            "passed": passed,
            "errors": errors,
        }
        results.append(rec)

        status = "PASS" if passed else "FAIL"
        print(
            f"[opencode] {idx}/{len(TASKS)} {task['id']}: {status} "
            f"(exit={run_info['exit_code']}, {run_info['duration_s']}s)"
        )
        if errors:
            for err in errors[:3]:
                print(f"  - {err}")

    passes = sum(1 for r in results if r["passed"])
    summary = {
        "by_harness": {"opencode": {"passes": passes, "total": len(results)}},
        "overall_passes": passes,
        "overall_total": len(results),
    }
    payload = {
        "config": {
            "openai_base_url": hb.OPENAI_BASE_URL,
            "opencode_model": hb.OPENCODE_MODEL,
            "suite": "hard90",
        },
        "results": results,
        "summary": summary,
    }
    hb.save_text(run_dir / "results.json", json.dumps(payload, indent=2))

    print("\nSummary:")
    print(f"- opencode: {passes}/{len(results)}")
    print(f"- overall: {passes}/{len(results)}")
    print(f"- artifacts: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
