#!/usr/bin/env python3
import itertools
import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

import harness_benchmark as hb


TaskChecker = Callable[[Dict[str, Any]], List[str]]


def check_max_flow_dinic(ns: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    fn = ns.get("max_flow_dinic")
    if not callable(fn):
        return ["Missing callable max_flow_dinic(n, edges, s, t)."]
    cases = [
        (4, [(0, 1, 3), (0, 2, 2), (1, 2, 1), (1, 3, 2), (2, 3, 4)], 0, 3, 5),
        (5, [(0, 1, 10), (1, 2, 5), (2, 1, 3), (2, 4, 7)], 0, 4, 5),
        (3, [(0, 1, 1)], 0, 2, 0),
    ]
    for n, edges, s, t, expected in cases:
        try:
            got = fn(n, edges, s, t)
            if got != expected:
                errors.append(f"max_flow_dinic({n}, edges, {s}, {t}) -> {got}, expected {expected}")
        except Exception as exc:
            errors.append(f"Exception in max_flow_dinic case {n}: {exc}")
    return errors


def check_min_cost_max_flow(ns: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    fn = ns.get("min_cost_max_flow")
    if not callable(fn):
        return ["Missing callable min_cost_max_flow(n, edges, s, t, k)."]
    edges = [
        (0, 1, 2, 1),
        (0, 2, 1, 5),
        (1, 2, 1, 1),
        (1, 3, 1, 3),
        (2, 3, 2, 1),
    ]
    cases = [
        (4, edges, 0, 3, 2, 7),
        (4, edges, 0, 3, 3, 13),
        (4, edges, 0, 3, 4, -1),
    ]
    for n, e, s, t, k, expected in cases:
        try:
            got = fn(n, e, s, t, k)
            if got != expected:
                errors.append(
                    f"min_cost_max_flow({n}, edges, {s}, {t}, {k}) -> {got}, expected {expected}"
                )
        except Exception as exc:
            errors.append(f"Exception in min_cost_max_flow case k={k}: {exc}")
    return errors


def check_solve_2sat(ns: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    fn = ns.get("solve_2sat")
    if not callable(fn):
        return ["Missing callable solve_2sat(num_vars, clauses)."]

    def lit_value(assign: List[bool], var: int, is_pos: bool) -> bool:
        return assign[var] if is_pos else (not assign[var])

    def clause_ok(assign: List[bool], clause: Tuple[int, bool, int, bool]) -> bool:
        a, apos, b, bpos = clause
        return lit_value(assign, a, apos) or lit_value(assign, b, bpos)

    sat_cases = [
        (2, [(0, True, 1, True), (0, False, 1, True), (0, True, 1, False)]),
        (3, [(0, True, 1, False), (1, True, 2, True), (0, False, 2, False)]),
    ]
    unsat_cases = [
        (1, [(0, True, 0, True), (0, False, 0, False)]),
        (2, [(0, True, 0, True), (0, False, 0, False), (1, True, 1, False)]),
    ]

    for n, clauses in sat_cases:
        try:
            sat, assign = fn(n, clauses)
            if sat is not True:
                errors.append(f"solve_2sat should return satisfiable for {clauses}")
                continue
            if not isinstance(assign, list) or len(assign) != n:
                errors.append(f"solve_2sat assignment malformed for {clauses}: {assign}")
                continue
            if not all(clause_ok(assign, c) for c in clauses):
                errors.append(f"solve_2sat returned invalid assignment for {clauses}: {assign}")
        except Exception as exc:
            errors.append(f"Exception in solve_2sat SAT case {clauses}: {exc}")

    for n, clauses in unsat_cases:
        try:
            sat, _assign = fn(n, clauses)
            if sat is not False:
                errors.append(f"solve_2sat should return unsat for {clauses}")
        except Exception as exc:
            errors.append(f"Exception in solve_2sat UNSAT case {clauses}: {exc}")
    return errors


def check_count_distinct_substrings(ns: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    fn = ns.get("count_distinct_substrings")
    if not callable(fn):
        return ["Missing callable count_distinct_substrings(s)."]
    cases = [
        ("", 0),
        ("aaa", 3),
        ("ababa", 9),
        ("abcd", 10),
    ]
    for s, expected in cases:
        try:
            got = fn(s)
            if got != expected:
                errors.append(f"count_distinct_substrings({s!r}) -> {got}, expected {expected}")
        except Exception as exc:
            errors.append(f"Exception in count_distinct_substrings({s!r}): {exc}")
    return errors


def check_longest_common_substring(ns: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    fn = ns.get("longest_common_substring")
    if not callable(fn):
        return ["Missing callable longest_common_substring(a, b)."]
    cases = [
        ("xabxac", "abcabxabcd", 4),
        ("abcdef", "zcdemf", 3),
        ("aaaa", "aa", 2),
        ("abc", "xyz", 0),
    ]
    for a, b, expected in cases:
        try:
            got = fn(a, b)
            if got != expected:
                errors.append(f"longest_common_substring({a!r}, {b!r}) -> {got}, expected {expected}")
        except Exception as exc:
            errors.append(f"Exception in longest_common_substring({a!r}, {b!r}): {exc}")
    return errors


def check_kth_smallest_pair_distance(ns: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    fn = ns.get("kth_smallest_pair_distance")
    if not callable(fn):
        return ["Missing callable kth_smallest_pair_distance(nums, k)."]
    cases = [
        ([1, 3, 1], 1, 0),
        ([1, 1, 1], 2, 0),
        ([1, 6, 1], 3, 5),
    ]
    for nums, k, expected in cases:
        try:
            got = fn(nums, k)
            if got != expected:
                errors.append(f"kth_smallest_pair_distance({nums}, {k}) -> {got}, expected {expected}")
        except Exception as exc:
            errors.append(f"Exception in kth_smallest_pair_distance({nums}, {k}): {exc}")
    return errors


def check_smallest_sufficient_team(ns: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    fn = ns.get("smallest_sufficient_team")
    if not callable(fn):
        return ["Missing callable smallest_sufficient_team(req_skills, people)."]

    def min_team_size(req_skills: List[str], people: List[List[str]]) -> int:
        skill_idx = {s: i for i, s in enumerate(req_skills)}
        target = (1 << len(req_skills)) - 1
        masks = []
        for p in people:
            m = 0
            for s in p:
                if s in skill_idx:
                    m |= 1 << skill_idx[s]
            masks.append(m)
        best = len(people) + 1
        for r in range(1, len(people) + 1):
            for combo in itertools.combinations(range(len(people)), r):
                m = 0
                for i in combo:
                    m |= masks[i]
                if m == target:
                    return r
        return best

    def covers(req_skills: List[str], people: List[List[str]], team: List[int]) -> bool:
        have = set()
        for i in team:
            if i < 0 or i >= len(people):
                return False
            have.update(people[i])
        return all(s in have for s in req_skills)

    cases = [
        (
            ["java", "nodejs", "reactjs"],
            [["java"], ["nodejs"], ["nodejs", "reactjs"]],
        ),
        (
            ["algorithms", "math", "java", "reactjs", "csharp", "aws"],
            [["algorithms", "math", "java"], ["algorithms", "math", "reactjs"], ["java", "csharp", "aws"],
             ["reactjs", "csharp"], ["csharp", "math"], ["aws", "java"]],
        ),
    ]
    for req_skills, people in cases:
        try:
            team = fn(req_skills, people)
            if not isinstance(team, list):
                errors.append(f"smallest_sufficient_team returned non-list: {type(team)}")
                continue
            if not covers(req_skills, people, team):
                errors.append(f"Returned team does not cover all skills: {team}")
                continue
            optimal = min_team_size(req_skills, people)
            if len(team) != optimal:
                errors.append(f"Returned team size {len(team)} not optimal {optimal}; team={team}")
        except Exception as exc:
            errors.append(f"Exception in smallest_sufficient_team case: {exc}")
    return errors


def check_min_cost_to_cut_stick(ns: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    fn = ns.get("min_cost_to_cut_stick")
    if not callable(fn):
        return ["Missing callable min_cost_to_cut_stick(n, cuts)."]
    cases = [
        (7, [1, 3, 4, 5], 16),
        (9, [5, 6, 1, 4, 2], 22),
        (100, [], 0),
    ]
    for n, cuts, expected in cases:
        try:
            got = fn(n, cuts)
            if got != expected:
                errors.append(f"min_cost_to_cut_stick({n}, {cuts}) -> {got}, expected {expected}")
        except Exception as exc:
            errors.append(f"Exception in min_cost_to_cut_stick({n}, {cuts}): {exc}")
    return errors


def check_max_sum_three_subarrays(ns: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    fn = ns.get("max_sum_of_3_non_overlapping_subarrays")
    if not callable(fn):
        return ["Missing callable max_sum_of_3_non_overlapping_subarrays(nums, k)."]
    cases = [
        ([1, 2, 1, 2, 6, 7, 5, 1], 2, [0, 3, 5]),
        ([1, 2, 1, 2, 1, 2, 1, 2, 1], 2, [0, 2, 4]),
    ]
    for nums, k, expected in cases:
        try:
            got = fn(nums, k)
            if got != expected:
                errors.append(
                    f"max_sum_of_3_non_overlapping_subarrays({nums}, {k}) -> {got}, expected {expected}"
                )
        except Exception as exc:
            errors.append(f"Exception in max_sum_of_3_non_overlapping_subarrays case: {exc}")
    return errors


def check_median_stream(ns: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    fn = ns.get("median_stream")
    if not callable(fn):
        return ["Missing callable median_stream(ops)."]
    cases = [
        ([("add", 1), ("add", 2), ("median", None), ("add", 3), ("median", None)], [1.5, 2.0]),
        ([("add", -1), ("median", None), ("add", -2), ("median", None), ("add", 4), ("median", None)],
         [-1.0, -1.5, -1.0]),
    ]
    for ops, expected in cases:
        try:
            got = fn(ops)
            if not isinstance(got, list):
                errors.append(f"median_stream returned non-list: {type(got)}")
                continue
            gotf = [float(x) for x in got]
            if gotf != expected:
                errors.append(f"median_stream({ops}) -> {gotf}, expected {expected}")
        except Exception as exc:
            errors.append(f"Exception in median_stream case {ops}: {exc}")
    return errors


TASKS: List[Dict[str, Any]] = [
    {
        "id": "hard90v2_max_flow_dinic",
        "title": "Max Flow (Dinic)",
        "difficulty_0_100": 92,
        "description": (
            "Implement: def max_flow_dinic(n: int, edges: list[tuple[int,int,int]], s: int, t: int) -> int. "
            "Edges are directed with capacities."
        ),
        "checker": check_max_flow_dinic,
    },
    {
        "id": "hard90v2_min_cost_max_flow",
        "title": "Min-Cost Max-Flow",
        "difficulty_0_100": 95,
        "description": (
            "Implement: def min_cost_max_flow(n: int, edges: list[tuple[int,int,int,int]], s: int, t: int, k: int) -> int. "
            "Return minimum cost to send exactly k units of flow, or -1 if impossible."
        ),
        "checker": check_min_cost_max_flow,
    },
    {
        "id": "hard90v2_2sat",
        "title": "2-SAT Solver",
        "difficulty_0_100": 91,
        "description": (
            "Implement: def solve_2sat(num_vars: int, clauses: list[tuple[int,bool,int,bool]]) -> tuple[bool, list[bool]]. "
            "Each clause tuple (a, apos, b, bpos) means literal(a,apos) OR literal(b,bpos)."
        ),
        "checker": check_solve_2sat,
    },
    {
        "id": "hard90v2_count_distinct_substrings",
        "title": "Count Distinct Substrings",
        "difficulty_0_100": 90,
        "description": "Implement: def count_distinct_substrings(s: str) -> int.",
        "checker": check_count_distinct_substrings,
    },
    {
        "id": "hard90v2_longest_common_substring",
        "title": "Longest Common Substring",
        "difficulty_0_100": 90,
        "description": "Implement: def longest_common_substring(a: str, b: str) -> int.",
        "checker": check_longest_common_substring,
    },
    {
        "id": "hard90v2_kth_pair_distance",
        "title": "K-th Smallest Pair Distance",
        "difficulty_0_100": 90,
        "description": "Implement: def kth_smallest_pair_distance(nums: list[int], k: int) -> int.",
        "checker": check_kth_smallest_pair_distance,
    },
    {
        "id": "hard90v2_smallest_sufficient_team",
        "title": "Smallest Sufficient Team",
        "difficulty_0_100": 90,
        "description": (
            "Implement: def smallest_sufficient_team(req_skills: list[str], people: list[list[str]]) -> list[int]."
        ),
        "checker": check_smallest_sufficient_team,
    },
    {
        "id": "hard90v2_cut_stick",
        "title": "Minimum Cost to Cut a Stick",
        "difficulty_0_100": 90,
        "description": "Implement: def min_cost_to_cut_stick(n: int, cuts: list[int]) -> int.",
        "checker": check_min_cost_to_cut_stick,
    },
    {
        "id": "hard90v2_three_subarrays",
        "title": "Max Sum of 3 Non-Overlapping Subarrays",
        "difficulty_0_100": 90,
        "description": (
            "Implement: def max_sum_of_3_non_overlapping_subarrays(nums: list[int], k: int) -> list[int]. "
            "Return lexicographically smallest indices on ties."
        ),
        "checker": check_max_sum_three_subarrays,
    },
    {
        "id": "hard90v2_median_stream",
        "title": "Median Data Stream Processor",
        "difficulty_0_100": 90,
        "description": (
            "Implement: def median_stream(ops: list[tuple[str, int | None]]) -> list[float]. "
            "Each op is ('add', value) or ('median', None). Return medians in query order."
        ),
        "checker": check_median_stream,
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
    run_dir = hb.RESULTS_DIR / f"run-{run_ts}-hard90v2-gemma4"
    run_dir.mkdir(parents=True, exist_ok=True)

    harnesses = os.environ.get("BENCH_HARNESSES", "opencode").strip()
    selected_harnesses = [h.strip() for h in harnesses.split(",") if h.strip()]
    if not selected_harnesses:
        selected_harnesses = ["opencode"]

    results: List[Dict[str, Any]] = []
    for harness in selected_harnesses:
        for idx, task in enumerate(TASKS, start=1):
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
                f"[{harness}] {idx}/{len(TASKS)} {task['id']}: {status} "
                f"(exit={run_info['exit_code']}, {run_info['duration_s']}s)"
            )
            if errors:
                for err in errors[:3]:
                    print(f"  - {err}")

    summary: Dict[str, Any] = {"by_harness": {}, "overall_passes": 0, "overall_total": len(results)}
    for harness in selected_harnesses:
        subset = [r for r in results if r["harness"] == harness]
        passes = sum(1 for r in subset if r["passed"])
        summary["by_harness"][harness] = {"passes": passes, "total": len(subset)}
        summary["overall_passes"] += passes

    payload = {
        "config": {
            "openai_base_url": hb.OPENAI_BASE_URL,
            "opencode_model": hb.OPENCODE_MODEL,
            "qwen_model": hb.QWEN_MODEL,
            "codex_model": hb.CODEX_MODEL,
            "claude_model": hb.CLAUDE_MODEL,
            "suite": "hard90_v2",
            "harnesses": selected_harnesses,
        },
        "results": results,
        "summary": summary,
    }
    hb.save_text(run_dir / "results.json", json.dumps(payload, indent=2))

    print("\nSummary:")
    for harness in selected_harnesses:
        row = summary["by_harness"][harness]
        print(f"- {harness}: {row['passes']}/{row['total']}")
    print(f"- overall: {summary['overall_passes']}/{summary['overall_total']}")
    print(f"- artifacts: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
