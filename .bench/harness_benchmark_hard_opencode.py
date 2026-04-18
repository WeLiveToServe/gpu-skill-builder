#!/usr/bin/env python3
import json
import math
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

import harness_benchmark as hb


TaskChecker = Callable[[Dict[str, Any]], List[str]]


def _approx_list_eq(a: List[float], b: List[float], eps: float = 1e-9) -> bool:
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if abs(x - y) > eps:
            return False
    return True


def check_sliding_window_median(ns: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    fn = ns.get("median_sliding_window")
    if not callable(fn):
        return ["Missing callable median_sliding_window(nums, k)."]
    cases = [
        ([1, 3, -1, -3, 5, 3, 6, 7], 3, [1.0, -1.0, -1.0, 3.0, 5.0, 6.0]),
        ([1, 2, 3, 4], 2, [1.5, 2.5, 3.5]),
        ([5, 5, 8, 1, 1, 3], 4, [5.0, 3.0, 2.0]),
    ]
    for nums, k, expected in cases:
        try:
            got = fn(nums, k)
            if not isinstance(got, list):
                errors.append(f"Expected list result for nums={nums}, k={k}, got {type(got)}")
                continue
            gotf = [float(x) for x in got]
            if not _approx_list_eq(gotf, expected):
                errors.append(f"median_sliding_window({nums}, {k}) -> {gotf}, expected {expected}")
        except Exception as exc:
            errors.append(f"Exception for median_sliding_window({nums}, {k}): {exc}")
    return errors


def check_trap_rain_water_2d(ns: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    fn = ns.get("trap_rain_water_2d")
    if not callable(fn):
        return ["Missing callable trap_rain_water_2d(height_map)."]
    cases = [
        (
            [
                [1, 4, 3, 1, 3, 2],
                [3, 2, 1, 3, 2, 4],
                [2, 3, 3, 2, 3, 1],
            ],
            4,
        ),
        (
            [
                [3, 3, 3, 3, 3],
                [3, 2, 2, 2, 3],
                [3, 2, 1, 2, 3],
                [3, 2, 2, 2, 3],
                [3, 3, 3, 3, 3],
            ],
            10,
        ),
        ([[5]], 0),
    ]
    for grid, expected in cases:
        try:
            got = fn(grid)
            if got != expected:
                errors.append(f"trap_rain_water_2d(...) -> {got}, expected {expected}")
        except Exception as exc:
            errors.append(f"Exception for trap_rain_water_2d case: {exc}")
    return errors


def _contains_all_words(s: str, words: List[str]) -> bool:
    return all(w in s for w in words)


def check_shortest_superstring(ns: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    fn = ns.get("shortest_superstring")
    if not callable(fn):
        return ["Missing callable shortest_superstring(words)."]
    # Expected lengths for these curated sets are stable.
    cases = [
        (["alex", "loves", "leetcode"], 17),
        (["catg", "ctaagt", "gcta", "ttca", "atgcatc"], 16),
        (["abcd", "bc", "cdef"], 6),
    ]
    for words, expected_len in cases:
        try:
            got = fn(words)
            if not isinstance(got, str):
                errors.append(f"shortest_superstring({words}) returned non-str: {type(got)}")
                continue
            if not _contains_all_words(got, words):
                errors.append(f"Result does not contain all words for {words}: {got!r}")
                continue
            if len(got) != expected_len:
                errors.append(
                    f"shortest_superstring({words}) length -> {len(got)}, expected {expected_len}; value={got!r}"
                )
        except Exception as exc:
            errors.append(f"Exception for shortest_superstring({words}): {exc}")
    return errors


def check_lfu_cache(ns: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    cls = ns.get("LFUCache")
    if cls is None:
        return ["Missing LFUCache class."]
    try:
        c = cls(2)
        c.put(1, 1)
        c.put(2, 2)
        if c.get(1) != 1:
            errors.append("LFUCache get(1) should be 1")
        c.put(3, 3)  # evicts key 2
        if c.get(2) != -1:
            errors.append("LFUCache should evict key 2 first")
        if c.get(3) != 3:
            errors.append("LFUCache get(3) should be 3")
        c.put(4, 4)  # evicts key 1
        if c.get(1) != -1:
            errors.append("LFUCache should evict key 1")
        if c.get(3) != 3:
            errors.append("LFUCache get(3) should still be 3")
        if c.get(4) != 4:
            errors.append("LFUCache get(4) should be 4")

        c2 = cls(0)
        c2.put(1, 1)
        if c2.get(1) != -1:
            errors.append("LFUCache with capacity 0 should never store values")
    except Exception as exc:
        errors.append(f"Exception while testing LFUCache: {exc}")
    return errors


def check_count_smaller(ns: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    fn = ns.get("count_smaller")
    if not callable(fn):
        return ["Missing callable count_smaller(nums)."]
    cases = [
        ([5, 2, 6, 1], [2, 1, 1, 0]),
        ([-1], [0]),
        ([-1, -1], [0, 0]),
        ([3, 2, 2, 6, 1], [3, 1, 1, 1, 0]),
    ]
    for nums, expected in cases:
        try:
            got = fn(nums)
            if got != expected:
                errors.append(f"count_smaller({nums}) -> {got}, expected {expected}")
        except Exception as exc:
            errors.append(f"Exception for count_smaller({nums}): {exc}")
    return errors


TASKS: List[Dict[str, Any]] = [
    {
        "id": "hard1_sliding_window_median",
        "title": "Sliding Window Median",
        "difficulty_0_100": 80,
        "description": (
            "Implement: def median_sliding_window(nums: list[int], k: int) -> list[float]. "
            "Return the median for each window of size k. "
            "For even k, median is average of two middle elements."
        ),
        "checker": check_sliding_window_median,
    },
    {
        "id": "hard2_trapping_rain_2d",
        "title": "Trapping Rain Water II",
        "difficulty_0_100": 82,
        "description": (
            "Implement: def trap_rain_water_2d(height_map: list[list[int]]) -> int. "
            "Given a 2D elevation map, compute total trapped rainwater."
        ),
        "checker": check_trap_rain_water_2d,
    },
    {
        "id": "hard3_shortest_superstring",
        "title": "Shortest Superstring",
        "difficulty_0_100": 84,
        "description": (
            "Implement: def shortest_superstring(words: list[str]) -> str. "
            "Return a shortest string containing each word as a substring."
        ),
        "checker": check_shortest_superstring,
    },
    {
        "id": "hard4_lfu_cache",
        "title": "LFU Cache",
        "difficulty_0_100": 79,
        "description": (
            "Implement class LFUCache with methods get(key)->int and put(key,value)->None. "
            "Evict least frequently used; break ties by least recently used."
        ),
        "checker": check_lfu_cache,
    },
    {
        "id": "hard5_count_smaller",
        "title": "Count of Smaller Numbers After Self",
        "difficulty_0_100": 81,
        "description": (
            "Implement: def count_smaller(nums: list[int]) -> list[int]. "
            "For each index i, return number of elements to the right that are smaller than nums[i]."
        ),
        "checker": check_count_smaller,
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
    run_dir = hb.RESULTS_DIR / f"run-{run_ts}-opencode-gemma4-hard80"
    run_dir.mkdir(parents=True, exist_ok=True)

    results: List[Dict[str, Any]] = []
    for idx, task in enumerate(TASKS, start=1):
        prompt = build_prompt(task)
        run_info = hb.run_opencode(prompt, timeout_s=420)
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
            "suite": "hard80",
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
