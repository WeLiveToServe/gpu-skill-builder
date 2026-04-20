#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple


BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "benchmark-results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

OPENAI_BASE_URL = os.environ.get("BENCH_OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
ANTHROPIC_BASE_URL = os.environ.get("BENCH_ANTHROPIC_BASE_URL", "https://openrouter.ai/api")
QWEN_MODEL = os.environ.get("BENCH_QWEN_MODEL", "qwen/qwen3.6-plus")
OPENCODE_MODEL = os.environ.get(
    "BENCH_OPENCODE_MODEL", "openrouter/qwen/qwen3.6-plus"
)
CODEX_MODEL = os.environ.get("BENCH_CODEX_MODEL", "qwen/qwen3.6-plus")
CLAUDE_MODEL = os.environ.get("BENCH_CLAUDE_MODEL", "qwen/qwen3.6-plus")

NPM_BIN_DIR = Path(os.environ.get("APPDATA", "")) / "npm"
QWEN_CLI = os.environ.get("BENCH_QWEN_CLI", str(NPM_BIN_DIR / "qwen.cmd"))
OPENCODE_CLI = os.environ.get("BENCH_OPENCODE_CLI", str(NPM_BIN_DIR / "opencode.cmd"))
CODEX_CLI = os.environ.get("BENCH_CODEX_CLI", str(NPM_BIN_DIR / "codex.cmd"))
CLAUDE_CLI = os.environ.get("BENCH_CLAUDE_CLI", str(NPM_BIN_DIR / "claude.cmd"))

GOOSE_CLI = os.environ.get("BENCH_GOOSE_CLI", str(Path.home() / ".local" / "bin" / "goose"))
GOOSE_MODEL = os.environ.get("BENCH_GOOSE_MODEL", "q")

HARNESS_ORDER = ["qwen", "opencode", "codex", "claude", "goose"]


def _cli_name(path_like: str) -> str:
    return Path(path_like).name.lower()


def _is_codexopen_cli(path_like: str) -> bool:
    return _cli_name(path_like) == "codexopen.cmd"


def _is_claudeopen_cli(path_like: str) -> bool:
    return _cli_name(path_like) == "claudeopen.cmd"


def _is_qwen_wrapper_cli(path_like: str) -> bool:
    # Local wrapper path and PATH-installed wrapper are both `qwen.cmd`.
    return _cli_name(path_like) == "qwen.cmd"


def _is_opencode_wrapper_cli(path_like: str) -> bool:
    # Local wrapper path and PATH-installed wrapper are both `opencode.cmd`.
    return _cli_name(path_like) == "opencode.cmd"


def run_cmd(
    cmd: List[str], env: Dict[str, str], timeout_s: int, input_text: str | None = None,
    cwd: str | None = None,
) -> Dict[str, Any]:
    start = time.time()
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=timeout_s,
        shell=False,
        input=input_text,
        cwd=cwd,
    )
    return {
        "exit_code": proc.returncode,
        "stdout": proc.stdout or "",
        "stderr": proc.stderr or "",
        "duration_s": round(time.time() - start, 3),
        "cmd": cmd,
    }


def strip_ansi(text: str) -> str:
    return re.sub(r"\x1B\[[0-9;]*[A-Za-z]", "", text)


def strip_wrapper_banner_lines(text: str) -> str:
    filtered: List[str] = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("[codexopen]") or s.startswith("[claudeopen]") or s.startswith("[qwen]") or s.startswith("[opencode]"):
            continue
        if s.startswith("> build"):
            continue
        filtered.append(line)
    return "\n".join(filtered).strip()


def extract_code(response_text: str) -> str:
    patterns = [
        r"PYTHON_START\s*(.*?)\s*PYTHON_END",
        r"BEGIN_CODE\s*```(?:python)?\s*(.*?)```[\r\n\s]*END_CODE",
        r"```(?:python)?\s*(.*?)```",
    ]
    for pat in patterns:
        m = re.search(pat, response_text, flags=re.IGNORECASE | re.DOTALL)
        if m:
            return m.group(1).strip()
    fallback = response_text.strip()
    m = re.search(
        r"(?ms)^(?:from\s+\w+|import\s+\w+|class\s+\w+|def\s+\w+).*$", fallback
    )
    if m:
        return m.group(0).strip()
    return fallback


def valid_topo(order: List[int], n: int, edges: List[Tuple[int, int]]) -> bool:
    if len(order) != n:
        return False
    if sorted(order) != list(range(n)):
        return False
    pos = {node: i for i, node in enumerate(order)}
    return all(pos[u] < pos[v] for u, v in edges)


def check_longest_consecutive(ns: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    fn = ns.get("longest_consecutive")
    if not callable(fn):
        return ["Missing callable longest_consecutive(nums)."]
    cases = [
        ([100, 4, 200, 1, 3, 2], 4),
        ([0, 3, 7, 2, 5, 8, 4, 6, 0, 1], 9),
        ([], 0),
        ([1, 2, 0, 1], 3),
        ([9], 1),
    ]
    for arr, expected in cases:
        try:
            got = fn(arr)
            if got != expected:
                errors.append(f"longest_consecutive({arr}) -> {got}, expected {expected}")
        except Exception as exc:  # pragma: no cover
            errors.append(f"Exception for longest_consecutive({arr}): {exc}")
    return errors


def check_min_window(ns: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    fn = ns.get("min_window")
    if not callable(fn):
        return ["Missing callable min_window(s, t)."]
    cases = [
        ("ADOBECODEBANC", "ABC", "BANC"),
        ("a", "a", "a"),
        ("a", "aa", ""),
        ("bba", "ab", "ba"),
        ("aa", "aa", "aa"),
        ("ab", "b", "b"),
    ]
    for s, t, expected in cases:
        try:
            got = fn(s, t)
            if got != expected:
                errors.append(f"min_window({s!r}, {t!r}) -> {got!r}, expected {expected!r}")
        except Exception as exc:  # pragma: no cover
            errors.append(f"Exception for min_window({s!r}, {t!r}): {exc}")
    return errors


def check_coin_change(ns: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    fn = ns.get("coin_change")
    if not callable(fn):
        return ["Missing callable coin_change(coins, amount)."]
    cases = [
        ([1, 2, 5], 11, 3),
        ([2], 3, -1),
        ([1], 0, 0),
        ([1], 2, 2),
        ([2, 5, 10, 1], 27, 4),
        ([186, 419, 83, 408], 6249, 20),
    ]
    for coins, amount, expected in cases:
        try:
            got = fn(coins, amount)
            if got != expected:
                errors.append(
                    f"coin_change({coins}, {amount}) -> {got}, expected {expected}"
                )
        except Exception as exc:  # pragma: no cover
            errors.append(f"Exception for coin_change({coins}, {amount}): {exc}")
    return errors


def check_topo_sort(ns: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    fn = ns.get("topo_sort_lexicographic")
    if not callable(fn):
        return ["Missing callable topo_sort_lexicographic(n, edges)."]

    dag1_edges = [(0, 1), (0, 2), (1, 3), (2, 3)]
    dag2_edges = [(1, 2)]
    dag3_edges = [(0, 2), (1, 2), (1, 3), (3, 4)]
    cyc_edges = [(0, 1), (1, 0)]

    cases = [
        (4, dag1_edges, [0, 1, 2, 3], False),
        (3, dag2_edges, [0, 1, 2], False),
        (5, dag3_edges, [0, 1, 2, 3, 4], False),
        (2, cyc_edges, [], True),
    ]

    for n, edges, expected, is_cycle in cases:
        try:
            got = fn(n, edges)
            if is_cycle:
                if got != []:
                    errors.append(f"Expected [] for cycle case, got {got}")
                continue
            if not isinstance(got, list):
                errors.append(f"topo_sort_lexicographic returned non-list: {type(got)}")
                continue
            if not valid_topo(got, n, edges):
                errors.append(f"Invalid topological order for n={n}, edges={edges}: {got}")
                continue
            if got != expected:
                errors.append(
                    f"Expected lexicographically smallest order {expected}, got {got}"
                )
        except Exception as exc:  # pragma: no cover
            errors.append(f"Exception for topo case {n}, {edges}: {exc}")
    return errors


def check_time_map(ns: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    cls = ns.get("TimeMap")
    if cls is None:
        return ["Missing TimeMap class."]
    try:
        tm = cls()
        tm.set("foo", "bar", 1)
        if tm.get("foo", 1) != "bar":
            errors.append("TimeMap basic get at exact timestamp failed.")
        if tm.get("foo", 3) != "bar":
            errors.append("TimeMap basic get at later timestamp failed.")
        tm.set("foo", "bar2", 4)
        if tm.get("foo", 4) != "bar2":
            errors.append("TimeMap overwrite at newer timestamp failed.")
        if tm.get("foo", 5) != "bar2":
            errors.append("TimeMap latest value lookup failed.")
        if tm.get("foo", 0) != "":
            errors.append("TimeMap should return empty before first timestamp.")
        tm.set("key", "v1", 5)
        tm.set("key", "v2", 10)
        tm.set("key", "v3", 15)
        if tm.get("key", 14) != "v2":
            errors.append("TimeMap floor lookup failed at intermediate timestamp.")
        if tm.get("missing", 999) != "":
            errors.append("TimeMap missing key lookup should return empty string.")
    except Exception as exc:  # pragma: no cover
        errors.append(f"Exception while testing TimeMap: {exc}")
    return errors


TaskChecker = Callable[[Dict[str, Any]], List[str]]

TASKS: List[Dict[str, Any]] = [
    {
        "id": "task1_longest_consecutive",
        "title": "Longest Consecutive Sequence",
        "description": textwrap.dedent(
            """
            Implement:
            def longest_consecutive(nums: list[int]) -> int

            Return the length of the longest run of consecutive integers.
            Must run in O(n) average time using hash-based logic.
            """
        ).strip(),
        "checker": check_longest_consecutive,
    },
    {
        "id": "task2_min_window",
        "title": "Minimum Window Substring",
        "description": textwrap.dedent(
            """
            Implement:
            def min_window(s: str, t: str) -> str

            Return the smallest substring of s containing all characters in t
            including multiplicity. Return empty string when no such window exists.
            """
        ).strip(),
        "checker": check_min_window,
    },
    {
        "id": "task3_coin_change",
        "title": "Minimum Coin Change",
        "description": textwrap.dedent(
            """
            Implement:
            def coin_change(coins: list[int], amount: int) -> int

            Return the minimum number of coins needed to make amount.
            Return -1 if impossible.
            """
        ).strip(),
        "checker": check_coin_change,
    },
    {
        "id": "task4_topo_lexicographic",
        "title": "Lexicographic Topological Sort",
        "description": textwrap.dedent(
            """
            Implement:
            def topo_sort_lexicographic(n: int, edges: list[tuple[int, int]]) -> list[int]

            Return the lexicographically smallest valid topological ordering of nodes 0..n-1.
            Return [] if the graph has a cycle.
            """
        ).strip(),
        "checker": check_topo_sort,
    },
    {
        "id": "task5_timemap",
        "title": "TimeMap Data Structure",
        "description": textwrap.dedent(
            """
            Implement class:
            class TimeMap:
                def set(self, key: str, value: str, timestamp: int) -> None
                def get(self, key: str, timestamp: int) -> str

            For get, return the value set at the largest timestamp <= given timestamp,
            or empty string if no value exists.
            """
        ).strip(),
        "checker": check_time_map,
    },
]


def build_prompt(task: Dict[str, Any]) -> str:
    compact_task = " ".join(task["description"].split())
    return (
        "Solve this Python task. Output format is mandatory: "
        "PYTHON_START then valid Python source code then PYTHON_END. "
        "No prose. No markdown. "
        f"{compact_task}"
    )


def run_qwen(prompt: str, timeout_s: int = 240) -> Dict[str, Any]:
    env = os.environ.copy()
    if _is_qwen_wrapper_cli(QWEN_CLI):
        # Wrapper already injects OpenRouter auth + model wiring.
        cmd = [
            QWEN_CLI,
            "--prompt",
            prompt,
            "--output-format",
            "json",
            "--yolo",
        ]
    else:
        openrouter_key = env.get("OPENROUTER_API_KEY", "").strip()
        if not openrouter_key:
            raise RuntimeError("OPENROUTER_API_KEY must be set for qwen harness.")
        cmd = [
            QWEN_CLI,
            "--prompt",
            prompt,
            "--auth-type",
            "openai",
            "--openai-api-key",
            openrouter_key,
            "--openai-base-url",
            OPENAI_BASE_URL,
            "--model",
            QWEN_MODEL,
            "--output-format",
            "json",
            "--yolo",
        ]
    with tempfile.TemporaryDirectory() as tmp:
        out = run_cmd(cmd, env, timeout_s, cwd=tmp)
    response = strip_wrapper_banner_lines(out["stdout"])
    try:
        payload = json.loads(response.strip())
        if isinstance(payload, list):
            for item in reversed(payload):
                if item.get("type") == "result" and item.get("subtype") == "success":
                    response = item.get("result", response)
                    break
    except Exception:
        pass
    out["response_text"] = response
    return out


def run_opencode(prompt: str, timeout_s: int = 240) -> Dict[str, Any]:
    env = os.environ.copy()
    if _is_opencode_wrapper_cli(OPENCODE_CLI):
        # Wrapper sets model + provider config; avoid duplicating -m.
        cmd = [
            OPENCODE_CLI,
            "run",
            prompt,
            "--dangerously-skip-permissions",
            "--pure",
        ]
    else:
        openrouter_key = env.get("OPENROUTER_API_KEY", "").strip()
        if not openrouter_key:
            raise RuntimeError("OPENROUTER_API_KEY must be set for opencode harness.")
        env["OPENROUTER_API_KEY"] = openrouter_key
        cmd = [
            OPENCODE_CLI,
            "run",
            prompt,
            "-m",
            OPENCODE_MODEL,
            "--dangerously-skip-permissions",
            "--pure",
        ]
    with tempfile.TemporaryDirectory() as tmp:
        out = run_cmd(cmd, env, timeout_s, cwd=tmp)
    cleaned = strip_wrapper_banner_lines(strip_ansi(out["stdout"]))
    out["response_text"] = cleaned.strip()
    return out


def run_codex(prompt: str, result_file: Path, timeout_s: int = 300) -> Dict[str, Any]:
    env = os.environ.copy()
    openrouter_key = env.get("OPENROUTER_API_KEY", "").strip()
    if openrouter_key:
        env["OPENROUTER_API_KEY"] = openrouter_key
    with tempfile.TemporaryDirectory() as tmp:
        if _is_codexopen_cli(CODEX_CLI):
            cmd = [
                CODEX_CLI,
                "exec",
                "--skip-git-repo-check",
                "-C",
                tmp,
                "--dangerously-bypass-approvals-and-sandbox",
                "-o",
                str(result_file),
            ]
        else:
            if not openrouter_key:
                raise RuntimeError("OPENROUTER_API_KEY must be set for codex harness.")
            cmd = [
                CODEX_CLI,
                "exec",
                "--skip-git-repo-check",
                "-C",
                tmp,
                "--disable",
                "apps",
                "--disable",
                "plugins",
                "--disable",
                "personality",
                "--disable",
                "multi_agent",
                "--disable",
                "skill_mcp_dependency_install",
                "--disable",
                "tool_suggest",
                "--disable",
                "workspace_dependencies",
                "-c",
                f'model="{CODEX_MODEL}"',
                "-c",
                'model_provider="openrouter"',
                "-c",
                f'model_providers.openrouter={{name="openrouter",base_url="{OPENAI_BASE_URL}",env_key="OPENROUTER_API_KEY",wire_api="responses"}}',
                "--dangerously-bypass-approvals-and-sandbox",
                "-o",
                str(result_file),
            ]
        out = run_cmd(cmd, env, timeout_s, input_text=prompt, cwd=tmp)
    response = ""
    if result_file.exists():
        response = result_file.read_text(encoding="utf-8", errors="ignore").strip()
    if not response:
        response = out["stdout"].strip()
    out["response_text"] = response
    return out


def _extract_from_stream_json(raw: str) -> str:
    """
    Parse --output-format stream-json --verbose output.
    Collects all text deltas from assistant content blocks.
    Falls back to the summary result field if present.
    """
    texts: List[str] = []
    result_field = ""
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        t = obj.get("type", "")
        if t == "content_block_delta":
            delta = obj.get("delta", {})
            if delta.get("type") == "text_delta":
                texts.append(delta.get("text", ""))
        elif t == "assistant":
            for block in obj.get("message", {}).get("content", []):
                if block.get("type") == "text":
                    texts.append(block.get("text", ""))
        elif t == "result":
            result_field = obj.get("result", "")
    combined = "".join(texts).strip()
    return combined or result_field


def run_claude(prompt: str, timeout_s: int = 300) -> Dict[str, Any]:
    env = os.environ.copy()
    if _is_claudeopen_cli(CLAUDE_CLI):
        # stream-json + verbose surfaces the assistant message block,
        # which is where the response text lives when result field is empty.
        cmd = [
            CLAUDE_CLI,
            "-p",
            prompt,
            "--output-format",
            "stream-json",
            "--verbose",
            "--permission-mode",
            "bypassPermissions",
            "--dangerously-skip-permissions",
        ]
    else:
        openrouter_key = env.get("OPENROUTER_API_KEY", "").strip()
        if not openrouter_key:
            raise RuntimeError("OPENROUTER_API_KEY must be set for claude harness.")
        env["ANTHROPIC_API_KEY"] = openrouter_key
        env["ANTHROPIC_BASE_URL"] = ANTHROPIC_BASE_URL
        env["ANTHROPIC_CUSTOM_MODEL_OPTION"] = CLAUDE_MODEL
        env["ANTHROPIC_CUSTOM_MODEL_OPTION_NAME"] = f"OpenRouter: {CLAUDE_MODEL}"
        cmd = [
            CLAUDE_CLI,
            "-p",
            prompt,
            "--output-format",
            "stream-json",
            "--verbose",
            "--permission-mode",
            "bypassPermissions",
            "--dangerously-skip-permissions",
            "--model",
            CLAUDE_MODEL,
        ]
    # Run from a throw-away temp dir so Claude cannot write to repo files.
    with tempfile.TemporaryDirectory() as tmp:
        out = run_cmd(cmd, env, timeout_s, cwd=tmp)
    raw = strip_wrapper_banner_lines(out["stdout"])
    out["response_text"] = _extract_from_stream_json(raw)
    return out


def run_goose(prompt: str, timeout_s: int = 300) -> Dict[str, Any]:
    env = os.environ.copy()
    # Goose reads OPENAI_HOST for the base URL (no /v1 suffix)
    env["OPENAI_API_KEY"] = "dummy"
    env["OPENAI_HOST"] = OPENAI_BASE_URL.removesuffix("/v1")
    env["GOOSE_PROVIDER"] = "openai"
    env["GOOSE_MODEL"] = GOOSE_MODEL
    env["GOOSE_SKIP_TELEMETRY"] = "true"
    cmd = [
        GOOSE_CLI,
        "run",
        "--no-session",
        "--text",
        prompt,
        "--quiet",
    ]
    with tempfile.TemporaryDirectory() as tmp:
        out = run_cmd(cmd, env, timeout_s, cwd=tmp)
    response = strip_ansi(out["stdout"]).strip()
    out["response_text"] = response
    return out


def run_harness(harness: str, prompt: str, codex_result_file: Path) -> Dict[str, Any]:
    if harness == "qwen":
        return run_qwen(prompt)
    if harness == "opencode":
        return run_opencode(prompt)
    if harness == "codex":
        return run_codex(prompt, codex_result_file)
    if harness == "claude":
        return run_claude(prompt)
    if harness == "goose":
        return run_goose(prompt)
    raise ValueError(f"Unknown harness: {harness}")


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


def save_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> int:
    run_ts = int(time.time())
    run_dir = RESULTS_DIR / f"run-{run_ts}"
    run_dir.mkdir(parents=True, exist_ok=True)

    results: List[Dict[str, Any]] = []
    for harness in HARNESS_ORDER:
        for idx, task in enumerate(TASKS, start=1):
            task_prompt = build_prompt(task)
            key = f"{harness}_{task['id']}"
            codex_result_file = run_dir / "raw" / harness / f"{task['id']}.codex_last.txt"

            run_info = run_harness(harness, task_prompt, codex_result_file)
            response_text = run_info.get("response_text", "")
            code = extract_code(response_text)
            passed, errors = evaluate_code(task, code)

            save_text(run_dir / "raw" / harness / f"{task['id']}.stdout.txt", run_info["stdout"])
            save_text(run_dir / "raw" / harness / f"{task['id']}.stderr.txt", run_info["stderr"])
            save_text(run_dir / "parsed" / harness / f"{task['id']}.response.txt", response_text)
            save_text(run_dir / "parsed" / harness / f"{task['id']}.code.py", code)

            record = {
                "id": key,
                "harness": harness,
                "task_id": task["id"],
                "task_title": task["title"],
                "exit_code": run_info["exit_code"],
                "duration_s": run_info["duration_s"],
                "passed": passed,
                "errors": errors,
            }
            results.append(record)

            status = "PASS" if passed else "FAIL"
            print(
                f"[{harness}] {idx}/{len(TASKS)} {task['id']}: {status} "
                f"(exit={run_info['exit_code']}, {run_info['duration_s']}s)"
            )
            if errors:
                for err in errors[:3]:
                    print(f"  - {err}")

    summary: Dict[str, Any] = {"by_harness": {}, "overall_passes": 0, "overall_total": len(results)}
    for harness in HARNESS_ORDER:
        subset = [r for r in results if r["harness"] == harness]
        passes = sum(1 for r in subset if r["passed"])
        summary["by_harness"][harness] = {"passes": passes, "total": len(subset)}
        summary["overall_passes"] += passes

    payload = {"config": {
        "openai_base_url": OPENAI_BASE_URL,
        "anthropic_base_url": ANTHROPIC_BASE_URL,
        "qwen_model": QWEN_MODEL,
        "opencode_model": OPENCODE_MODEL,
        "codex_model": CODEX_MODEL,
        "claude_model": CLAUDE_MODEL,
    }, "results": results, "summary": summary}

    save_text(run_dir / "results.json", json.dumps(payload, indent=2))

    print("\nSummary:")
    for harness in HARNESS_ORDER:
        row = summary["by_harness"][harness]
        print(f"- {harness}: {row['passes']}/{row['total']}")
    print(f"- overall: {summary['overall_passes']}/{summary['overall_total']}")
    print(f"- artifacts: {run_dir}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.TimeoutExpired as exc:
        print(f"Timeout while running command: {exc}", file=sys.stderr)
        raise
