#!/usr/bin/env python3
import itertools
from collections import defaultdict, deque
from typing import Any, Callable, Dict, List, Tuple


TaskChecker = Callable[[Dict[str, Any]], List[str]]


def _eq_set_of_lists(a: List[List[Any]], b: List[List[Any]]) -> bool:
    sa = {tuple(x) for x in a}
    sb = {tuple(x) for x in b}
    return sa == sb


def check_max_flow_dinic(ns: Dict[str, Any]) -> List[str]:
    errors = []
    fn = ns.get("max_flow_dinic")
    if not callable(fn):
        return ["Missing callable max_flow_dinic(n, edges, s, t)."]
    cases = [
        (4, [(0, 1, 3), (0, 2, 2), (1, 2, 1), (1, 3, 2), (2, 3, 4)], 0, 3, 5),
        (5, [(0, 1, 10), (1, 2, 5), (2, 1, 3), (2, 4, 7)], 0, 4, 5),
    ]
    for n, edges, s, t, exp in cases:
        try:
            got = fn(n, edges, s, t)
            if got != exp:
                errors.append(f"max_flow_dinic case failed: got {got}, expected {exp}")
        except Exception as exc:
            errors.append(f"max_flow_dinic exception: {exc}")
    return errors


def check_min_cost_max_flow(ns: Dict[str, Any]) -> List[str]:
    errors = []
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
    cases = [(4, edges, 0, 3, 2, 7), (4, edges, 0, 3, 3, 13), (4, edges, 0, 3, 4, -1)]
    for n, e, s, t, k, exp in cases:
        try:
            got = fn(n, e, s, t, k)
            if got != exp:
                errors.append(f"min_cost_max_flow case failed: got {got}, expected {exp}")
        except Exception as exc:
            errors.append(f"min_cost_max_flow exception: {exc}")
    return errors


def check_solve_2sat(ns: Dict[str, Any]) -> List[str]:
    errors = []
    fn = ns.get("solve_2sat")
    if not callable(fn):
        return ["Missing callable solve_2sat(num_vars, clauses)."]

    def lit(assign: List[bool], var: int, pos: bool) -> bool:
        return assign[var] if pos else (not assign[var])

    def sat_ok(assign: List[bool], clauses: List[Tuple[int, bool, int, bool]]) -> bool:
        return all(lit(assign, a, ap) or lit(assign, b, bp) for a, ap, b, bp in clauses)

    sat_cases = [
        (2, [(0, True, 1, True), (0, False, 1, True), (0, True, 1, False)]),
        (3, [(0, True, 1, False), (1, True, 2, True), (0, False, 2, False)]),
    ]
    unsat_cases = [
        (1, [(0, True, 0, True), (0, False, 0, False)]),
    ]
    for n, clauses in sat_cases:
        try:
            sat, assign = fn(n, clauses)
            if sat is not True or not isinstance(assign, list) or len(assign) != n or not sat_ok(assign, clauses):
                errors.append(f"solve_2sat SAT case failed: {clauses}, got {(sat, assign)}")
        except Exception as exc:
            errors.append(f"solve_2sat SAT exception: {exc}")
    for n, clauses in unsat_cases:
        try:
            sat, _assign = fn(n, clauses)
            if sat is not False:
                errors.append(f"solve_2sat UNSAT case failed: {clauses}, got {sat}")
        except Exception as exc:
            errors.append(f"solve_2sat UNSAT exception: {exc}")
    return errors


def check_shortest_superstring(ns: Dict[str, Any]) -> List[str]:
    errors = []
    fn = ns.get("shortest_superstring")
    if not callable(fn):
        return ["Missing callable shortest_superstring(words)."]
    cases = [
        (["alex", "loves", "leetcode"], 17),
        (["catg", "ctaagt", "gcta", "ttca", "atgcatc"], 16),
        (["abcd", "bc", "cdef"], 6),
    ]
    for words, exp_len in cases:
        try:
            got = fn(words)
            if not isinstance(got, str):
                errors.append(f"shortest_superstring returned non-str: {type(got)}")
                continue
            if any(w not in got for w in words):
                errors.append(f"shortest_superstring missing word for {words}: {got!r}")
                continue
            if len(got) != exp_len:
                errors.append(f"shortest_superstring length {len(got)} != {exp_len} for {words}, got {got!r}")
        except Exception as exc:
            errors.append(f"shortest_superstring exception: {exc}")
    return errors


def check_count_range_sum(ns: Dict[str, Any]) -> List[str]:
    errors = []
    fn = ns.get("count_range_sum")
    if not callable(fn):
        return ["Missing callable count_range_sum(nums, lower, upper)."]
    cases = [
        ([-2, 5, -1], -2, 2, 3),
        ([0], 0, 0, 1),
        ([1, -1, 1], 0, 1, 5),
    ]
    for nums, lo, hi, exp in cases:
        try:
            got = fn(nums, lo, hi)
            if got != exp:
                errors.append(f"count_range_sum failed for {nums}: got {got}, expected {exp}")
        except Exception as exc:
            errors.append(f"count_range_sum exception: {exc}")
    return errors


def check_merge_stones(ns: Dict[str, Any]) -> List[str]:
    errors = []
    fn = ns.get("merge_stones")
    if not callable(fn):
        return ["Missing callable merge_stones(stones, k)."]
    cases = [
        ([3, 2, 4, 1], 2, 20),
        ([3, 2, 4, 1], 3, -1),
        ([3, 5, 1, 2, 6], 3, 25),
    ]
    for stones, k, exp in cases:
        try:
            got = fn(stones, k)
            if got != exp:
                errors.append(f"merge_stones failed: got {got}, expected {exp}")
        except Exception as exc:
            errors.append(f"merge_stones exception: {exc}")
    return errors


def check_critical_pseudo(ns: Dict[str, Any]) -> List[str]:
    errors = []
    fn = ns.get("find_critical_and_pseudo_critical_edges")
    if not callable(fn):
        return ["Missing callable find_critical_and_pseudo_critical_edges(n, edges)."]
    cases = [
        (
            5,
            [(0, 1, 1), (1, 2, 1), (2, 3, 2), (0, 3, 2), (0, 4, 3), (3, 4, 3), (1, 4, 6)],
            ([0, 1], [2, 3, 4, 5]),
        ),
        (4, [(0, 1, 1), (1, 2, 1), (2, 3, 1), (0, 3, 1)], ([], [0, 1, 2, 3])),
    ]
    for n, edges, (exp_c, exp_p) in cases:
        try:
            got = fn(n, edges)
            if not isinstance(got, list) or len(got) != 2:
                errors.append(f"critical/pseudo malformed result: {got}")
                continue
            gc, gp = sorted(got[0]), sorted(got[1])
            if gc != sorted(exp_c) or gp != sorted(exp_p):
                errors.append(f"critical/pseudo mismatch: got {[gc,gp]} expected {[sorted(exp_c),sorted(exp_p)]}")
        except Exception as exc:
            errors.append(f"critical/pseudo exception: {exc}")
    return errors


def check_sum_dist_tree(ns: Dict[str, Any]) -> List[str]:
    errors = []
    fn = ns.get("sum_of_distances_in_tree")
    if not callable(fn):
        return ["Missing callable sum_of_distances_in_tree(n, edges)."]
    cases = [
        (6, [(0, 1), (0, 2), (2, 3), (2, 4), (2, 5)], [8, 12, 6, 10, 10, 10]),
        (1, [], [0]),
    ]
    for n, edges, exp in cases:
        try:
            got = fn(n, edges)
            if got != exp:
                errors.append(f"sum_of_distances_in_tree mismatch: got {got}, expected {exp}")
        except Exception as exc:
            errors.append(f"sum_of_distances_in_tree exception: {exc}")
    return errors


def check_min_stickers(ns: Dict[str, Any]) -> List[str]:
    errors = []
    fn = ns.get("min_stickers")
    if not callable(fn):
        return ["Missing callable min_stickers(stickers, target)."]
    cases = [
        (["with", "example", "science"], "thehat", 3),
        (["notice", "possible"], "basicbasic", -1),
        (["abc", "ab", "bc"], "aabbcc", 2),
    ]
    for stickers, target, exp in cases:
        try:
            got = fn(stickers, target)
            if got != exp:
                errors.append(f"min_stickers mismatch for {target}: got {got}, expected {exp}")
        except Exception as exc:
            errors.append(f"min_stickers exception: {exc}")
    return errors


def check_matrix_rank_transform(ns: Dict[str, Any]) -> List[str]:
    errors = []
    fn = ns.get("matrix_rank_transform")
    if not callable(fn):
        return ["Missing callable matrix_rank_transform(matrix)."]
    cases = [
        ([[1, 2], [3, 4]], [[1, 2], [2, 3]]),
        ([[7, 7], [7, 7]], [[1, 1], [1, 1]]),
        ([[20, -21, 14], [-19, 4, 19], [22, -47, 24], [-19, 4, 19]], [[4, 2, 3], [1, 3, 4], [5, 1, 6], [1, 3, 4]]),
    ]
    for m, exp in cases:
        try:
            got = fn(m)
            if got != exp:
                errors.append(f"matrix_rank_transform mismatch: got {got}, expected {exp}")
        except Exception as exc:
            errors.append(f"matrix_rank_transform exception: {exc}")
    return errors


def check_remove_invalid_parentheses(ns: Dict[str, Any]) -> List[str]:
    errors = []
    fn = ns.get("remove_invalid_parentheses")
    if not callable(fn):
        return ["Missing callable remove_invalid_parentheses(s)."]
    cases = [
        ("()())()", ["(())()", "()()()"]),
        ("(a)())()", ["(a())()", "(a)()()"]),
        (")(", [""]),
    ]
    for s, exp in cases:
        try:
            got = fn(s)
            if not isinstance(got, list):
                errors.append(f"remove_invalid_parentheses non-list for {s!r}: {type(got)}")
                continue
            if set(got) != set(exp):
                errors.append(f"remove_invalid_parentheses mismatch for {s!r}: got {got}, expected {exp}")
        except Exception as exc:
            errors.append(f"remove_invalid_parentheses exception: {exc}")
    return errors


def check_regex_match(ns: Dict[str, Any]) -> List[str]:
    errors = []
    fn = ns.get("is_match_regex")
    if not callable(fn):
        return ["Missing callable is_match_regex(s, p)."]
    cases = [
        ("aa", "a", False),
        ("aa", "a*", True),
        ("ab", ".*", True),
        ("aab", "c*a*b", True),
        ("mississippi", "mis*is*p*.", False),
    ]
    for s, p, exp in cases:
        try:
            got = fn(s, p)
            if got != exp:
                errors.append(f"is_match_regex({s!r},{p!r}) -> {got}, expected {exp}")
        except Exception as exc:
            errors.append(f"is_match_regex exception: {exc}")
    return errors


def check_wildcard_match(ns: Dict[str, Any]) -> List[str]:
    errors = []
    fn = ns.get("is_match_wildcard")
    if not callable(fn):
        return ["Missing callable is_match_wildcard(s, p)."]
    cases = [
        ("aa", "a", False),
        ("aa", "*", True),
        ("cb", "?a", False),
        ("adceb", "*a*b", True),
        ("acdcb", "a*c?b", False),
    ]
    for s, p, exp in cases:
        try:
            got = fn(s, p)
            if got != exp:
                errors.append(f"is_match_wildcard({s!r},{p!r}) -> {got}, expected {exp}")
        except Exception as exc:
            errors.append(f"is_match_wildcard exception: {exc}")
    return errors


def check_shortest_path_all_nodes(ns: Dict[str, Any]) -> List[str]:
    errors = []
    fn = ns.get("shortest_path_length_all_nodes")
    if not callable(fn):
        return ["Missing callable shortest_path_length_all_nodes(graph)."]
    cases = [
        ([[1, 2, 3], [0], [0], [0]], 4),
        ([[1], [0, 2, 4], [1, 3, 4], [2], [1, 2]], 4),
    ]
    for g, exp in cases:
        try:
            got = fn(g)
            if got != exp:
                errors.append(f"shortest_path_length_all_nodes -> {got}, expected {exp}")
        except Exception as exc:
            errors.append(f"shortest_path_length_all_nodes exception: {exc}")
    return errors


def check_max_points_on_line(ns: Dict[str, Any]) -> List[str]:
    errors = []
    fn = ns.get("max_points_on_line")
    if not callable(fn):
        return ["Missing callable max_points_on_line(points)."]
    cases = [
        ([(1, 1), (2, 2), (3, 3)], 3),
        ([(1, 1), (3, 2), (5, 3), (4, 1), (2, 3), (1, 4)], 4),
        ([(0, 0), (0, 0)], 2),
    ]
    for pts, exp in cases:
        try:
            got = fn(pts)
            if got != exp:
                errors.append(f"max_points_on_line -> {got}, expected {exp}")
        except Exception as exc:
            errors.append(f"max_points_on_line exception: {exc}")
    return errors


def check_kth_lex_number(ns: Dict[str, Any]) -> List[str]:
    errors = []
    fn = ns.get("find_kth_number_lexicographical")
    if not callable(fn):
        return ["Missing callable find_kth_number_lexicographical(n, k)."]
    cases = [
        (13, 2, 10),
        (100, 10, 17),
        (1000, 100, 188),
    ]
    for n, k, exp in cases:
        try:
            got = fn(n, k)
            if got != exp:
                errors.append(f"find_kth_number_lexicographical({n},{k}) -> {got}, expected {exp}")
        except Exception as exc:
            errors.append(f"find_kth_number_lexicographical exception: {exc}")
    return errors


def check_strange_printer(ns: Dict[str, Any]) -> List[str]:
    errors = []
    fn = ns.get("strange_printer")
    if not callable(fn):
        return ["Missing callable strange_printer(s)."]
    cases = [("aaabbb", 2), ("aba", 2), ("abcabc", 5)]
    for s, exp in cases:
        try:
            got = fn(s)
            if got != exp:
                errors.append(f"strange_printer({s!r}) -> {got}, expected {exp}")
        except Exception as exc:
            errors.append(f"strange_printer exception: {exc}")
    return errors


def check_word_ladder_ii(ns: Dict[str, Any]) -> List[str]:
    errors = []
    fn = ns.get("find_ladders")
    if not callable(fn):
        return ["Missing callable find_ladders(begin_word, end_word, word_list)."]
    cases = [
        ("hit", "cog", ["hot", "dot", "dog", "lot", "log", "cog"],
         [["hit", "hot", "dot", "dog", "cog"], ["hit", "hot", "lot", "log", "cog"]]),
        ("hit", "cog", ["hot", "dot", "dog", "lot", "log"], []),
    ]
    for b, e, wl, exp in cases:
        try:
            got = fn(b, e, wl)
            if not isinstance(got, list):
                errors.append(f"find_ladders non-list output: {type(got)}")
                continue
            if not _eq_set_of_lists(got, exp):
                errors.append(f"find_ladders mismatch: got {got}, expected {exp}")
        except Exception as exc:
            errors.append(f"find_ladders exception: {exc}")
    return errors


def check_split_array_largest_sum(ns: Dict[str, Any]) -> List[str]:
    errors = []
    fn = ns.get("split_array_largest_sum")
    if not callable(fn):
        return ["Missing callable split_array_largest_sum(nums, k)."]
    cases = [
        ([7, 2, 5, 10, 8], 2, 18),
        ([1, 2, 3, 4, 5], 2, 9),
        ([1, 4, 4], 3, 4),
    ]
    for nums, k, exp in cases:
        try:
            got = fn(nums, k)
            if got != exp:
                errors.append(f"split_array_largest_sum({nums},{k}) -> {got}, expected {exp}")
        except Exception as exc:
            errors.append(f"split_array_largest_sum exception: {exc}")
    return errors


def check_make_largest_island(ns: Dict[str, Any]) -> List[str]:
    errors = []
    fn = ns.get("make_largest_island")
    if not callable(fn):
        return ["Missing callable make_largest_island(grid)."]
    cases = [
        ([[1, 0], [0, 1]], 3),
        ([[1, 1], [1, 0]], 4),
        ([[1, 1], [1, 1]], 4),
    ]
    for grid, exp in cases:
        try:
            got = fn(grid)
            if got != exp:
                errors.append(f"make_largest_island -> {got}, expected {exp}")
        except Exception as exc:
            errors.append(f"make_largest_island exception: {exc}")
    return errors


TASKS: List[Dict[str, Any]] = [
    {"id": "x100_01_max_flow_dinic", "title": "Max Flow Dinic", "difficulty_0_100": 100,
     "description": "Implement: def max_flow_dinic(n: int, edges: list[tuple[int,int,int]], s: int, t: int) -> int.",
     "checker": check_max_flow_dinic},
    {"id": "x100_02_min_cost_max_flow", "title": "Min Cost Max Flow", "difficulty_0_100": 100,
     "description": "Implement: def min_cost_max_flow(n: int, edges: list[tuple[int,int,int,int]], s: int, t: int, k: int) -> int.",
     "checker": check_min_cost_max_flow},
    {"id": "x100_03_2sat", "title": "2-SAT", "difficulty_0_100": 100,
     "description": "Implement: def solve_2sat(num_vars: int, clauses: list[tuple[int,bool,int,bool]]) -> tuple[bool, list[bool]].",
     "checker": check_solve_2sat},
    {"id": "x100_04_shortest_superstring", "title": "Shortest Superstring", "difficulty_0_100": 100,
     "description": "Implement: def shortest_superstring(words: list[str]) -> str.",
     "checker": check_shortest_superstring},
    {"id": "x100_05_count_range_sum", "title": "Count Range Sum", "difficulty_0_100": 100,
     "description": "Implement: def count_range_sum(nums: list[int], lower: int, upper: int) -> int.",
     "checker": check_count_range_sum},
    {"id": "x100_06_merge_stones", "title": "Merge Stones", "difficulty_0_100": 100,
     "description": "Implement: def merge_stones(stones: list[int], k: int) -> int.",
     "checker": check_merge_stones},
    {"id": "x100_07_critical_pseudo", "title": "Critical/Pseudo MST Edges", "difficulty_0_100": 100,
     "description": "Implement: def find_critical_and_pseudo_critical_edges(n: int, edges: list[tuple[int,int,int]]) -> list[list[int]].",
     "checker": check_critical_pseudo},
    {"id": "x100_08_sum_dist_tree", "title": "Sum Distances in Tree", "difficulty_0_100": 100,
     "description": "Implement: def sum_of_distances_in_tree(n: int, edges: list[tuple[int,int]]) -> list[int].",
     "checker": check_sum_dist_tree},
    {"id": "x100_09_min_stickers", "title": "Min Stickers", "difficulty_0_100": 100,
     "description": "Implement: def min_stickers(stickers: list[str], target: str) -> int.",
     "checker": check_min_stickers},
    {"id": "x100_10_matrix_rank_transform", "title": "Matrix Rank Transform", "difficulty_0_100": 100,
     "description": "Implement: def matrix_rank_transform(matrix: list[list[int]]) -> list[list[int]].",
     "checker": check_matrix_rank_transform},
    {"id": "x100_11_remove_invalid_parentheses", "title": "Remove Invalid Parentheses", "difficulty_0_100": 100,
     "description": "Implement: def remove_invalid_parentheses(s: str) -> list[str].",
     "checker": check_remove_invalid_parentheses},
    {"id": "x100_12_regex_match", "title": "Regex Match", "difficulty_0_100": 100,
     "description": "Implement: def is_match_regex(s: str, p: str) -> bool supporting . and *.",
     "checker": check_regex_match},
    {"id": "x100_13_wildcard_match", "title": "Wildcard Match", "difficulty_0_100": 100,
     "description": "Implement: def is_match_wildcard(s: str, p: str) -> bool supporting ? and *.",
     "checker": check_wildcard_match},
    {"id": "x100_14_shortest_path_all_nodes", "title": "Shortest Path Visiting All Nodes", "difficulty_0_100": 100,
     "description": "Implement: def shortest_path_length_all_nodes(graph: list[list[int]]) -> int.",
     "checker": check_shortest_path_all_nodes},
    {"id": "x100_15_max_points_line", "title": "Max Points on a Line", "difficulty_0_100": 100,
     "description": "Implement: def max_points_on_line(points: list[tuple[int,int]]) -> int.",
     "checker": check_max_points_on_line},
    {"id": "x100_16_kth_lex_number", "title": "Kth Lexicographical Number", "difficulty_0_100": 100,
     "description": "Implement: def find_kth_number_lexicographical(n: int, k: int) -> int.",
     "checker": check_kth_lex_number},
    {"id": "x100_17_strange_printer", "title": "Strange Printer", "difficulty_0_100": 100,
     "description": "Implement: def strange_printer(s: str) -> int.",
     "checker": check_strange_printer},
    {"id": "x100_18_word_ladder_ii", "title": "Word Ladder II", "difficulty_0_100": 100,
     "description": "Implement: def find_ladders(begin_word: str, end_word: str, word_list: list[str]) -> list[list[str]].",
     "checker": check_word_ladder_ii},
    {"id": "x100_19_split_array_largest_sum", "title": "Split Array Largest Sum", "difficulty_0_100": 100,
     "description": "Implement: def split_array_largest_sum(nums: list[int], k: int) -> int.",
     "checker": check_split_array_largest_sum},
    {"id": "x100_20_make_largest_island", "title": "Make Largest Island", "difficulty_0_100": 100,
     "description": "Implement: def make_largest_island(grid: list[list[int]]) -> int.",
     "checker": check_make_largest_island},
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

