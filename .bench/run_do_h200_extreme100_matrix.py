#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
BENCH_DIR = Path(__file__).resolve().parent
JOB_RUNS_DIR = BENCH_DIR / "matrix-runs"
TASK_REGISTRY_PATH = BENCH_DIR / "task_suites_registry.json"
DO_STATE_PATH = REPO_ROOT / ".do_state.json"
DEFAULT_SSH_KEY = Path.home() / ".ssh" / "do_agent_ed25519"
DEFAULT_SERVICE_PATH = "/etc/systemd/system/vllm.service"
DEFAULT_ENV_PATH = "/etc/vllm/gpt-oss-120b.env"
DEFAULT_LOCAL_PORT = 18000
DEFAULT_REMOTE_PORT = 8000
BENCHMARK_PROFILE_ID = "digitalocean-gpt-oss-120b-h200x1-harness-eval"
MODEL_PROFILE_ID = "openai-gpt-oss-120b"
HARNESS_SEQUENCE = ("codex", "claude", "qwen")
OPTIONAL_HARNESS = "opencode"
SMOKE_FAILURE_PATTERNS = [
    re.compile(pattern, flags=re.IGNORECASE)
    for pattern in (
        r"\b401\b",
        r"\b403\b",
        r"\b404\b",
        r"\b429\b",
        r"api[ _-]?key",
        r"connection",
        r"connect",
        r"refused",
        r"timed out",
        r"timeout",
        r"unexpected error",
        r"no parseable json",
        r"\$\.split is not a function",
    )
]
FORMAT_FAILURE_PATTERNS = [
    re.compile(pattern, flags=re.IGNORECASE)
    for pattern in (
        r"invalid syntax",
        r"invalid decimal literal",
        r"no parseable json",
        r"no choices",
    )
]


sys.path.insert(0, str(REPO_ROOT))
from profile_registry import load_profile_registry  # noqa: E402
from remote_vllm import render_vllm_runtime_args  # noqa: E402


@dataclass
class JobLogger:
    path: Path

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("a", encoding="utf-8")

    def write(self, line: str) -> None:
        print(line)
        self._fh.write(f"{line}\n")
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()


def _parse_env_text(text: str) -> dict[str, str]:
    env: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


def _load_last_droplet_ip(state_path: Path) -> str:
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    return str(payload["last_droplet"]["ip"]).strip()


def _smoke_task_ids(suite_id: str, count: int) -> list[str]:
    registry = json.loads(TASK_REGISTRY_PATH.read_text(encoding="utf-8"))
    for suite in registry.get("suites", []):
        if suite.get("suite_id") == suite_id:
            return [str(task["task_id"]) for task in suite.get("tasks", [])[:count]]
    raise KeyError(f"Unknown suite_id {suite_id!r}")


def _trim_v1(url: str) -> str:
    stripped = url.rstrip("/")
    if stripped.endswith("/v1"):
        return stripped[:-3]
    return stripped


def _run_local(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    input_text: str | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        input=input_text,
        stdin=subprocess.DEVNULL if input_text is None else None,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        shell=False,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(
            "Command failed.\n"
            f"cmd={' '.join(cmd)}\n"
            f"exit={proc.returncode}\n"
            f"stdout={proc.stdout[-1000:]}\n"
            f"stderr={proc.stderr[-1000:]}"
        )
    return proc


def _run_ssh(
    *,
    host: str,
    ssh_key: Path,
    remote_args: list[str],
    input_text: str | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    if len(remote_args) >= 3 and remote_args[0] == "bash" and remote_args[1] == "-lc":
        remote_command = f"bash -lc {shlex.quote(remote_args[2])}"
    else:
        remote_command = " ".join(shlex.quote(arg) for arg in remote_args)
    cmd = [
        "ssh",
        "-i",
        str(ssh_key),
        "-T",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=30",
        "-o",
        "ServerAliveInterval=60",
        "-o",
        "ServerAliveCountMax=30",
        f"root@{host}",
        remote_command,
    ]
    return _run_local(cmd, input_text=input_text, check=check)


def _write_remote_text(*, host: str, ssh_key: Path, remote_path: str, content: str) -> None:
    quoted_path = remote_path.replace("'", "'\"'\"'")
    _run_ssh(
        host=host,
        ssh_key=ssh_key,
        remote_args=["bash", "-lc", f"cat > '{quoted_path}'"],
        input_text=content,
    )


def _render_benchmark_service(env_path: str) -> str:
    registry = load_profile_registry()
    model = registry.model_profiles[MODEL_PROFILE_ID]
    deployment = registry.deployment_profiles[BENCHMARK_PROFILE_ID]
    runtime_args = render_vllm_runtime_args(
        model_id="${MODEL_ID}",
        served_model_name="${SERVED_MODEL_NAME}",
        port="${PORT}",
        api_key="${VLLM_API_KEY}",
        download_dir="${HF_HOME}",
        runtime=deployment.runtime,
    )
    exec_start = " ".join(
        [
            "/usr/bin/docker",
            "run",
            "--rm",
            "--name",
            "${CONTAINER_NAME}",
            "--gpus",
            "all",
            "--network",
            "host",
            "--ipc=host",
            "--ulimit",
            "nofile=1048576:1048576",
            "-e",
            "CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES}",
            "-e",
            "HF_HOME=${HF_HOME}",
            "-e",
            "VLLM_ASSETS_CACHE=${VLLM_ASSETS_CACHE}",
            "-e",
            "HF_TOKEN=${HF_TOKEN}",
            "-e",
            "HUGGING_FACE_HUB_TOKEN=${HF_TOKEN}",
            "-v",
            "${HF_HOME}:${HF_HOME}",
            "-v",
            "${VLLM_ASSETS_CACHE}:${VLLM_ASSETS_CACHE}",
            "${IMAGE_REF}",
            *runtime_args,
        ]
    )
    return "\n".join(
        [
            "[Unit]",
            "Description=vLLM OpenAI-compatible server (gpt-oss-120b benchmark mode)",
            "After=network-online.target docker.service",
            "Wants=network-online.target",
            "Requires=docker.service",
            "",
            "[Service]",
            "Type=simple",
            "User=root",
            f"EnvironmentFile={env_path}",
            "ExecStartPre=-/usr/bin/docker rm -f ${CONTAINER_NAME}",
            f"ExecStart={exec_start}",
            "ExecStop=-/usr/bin/docker stop -t 30 ${CONTAINER_NAME}",
            "Restart=on-failure",
            "RestartSec=10",
            "TimeoutStartSec=0",
            "TimeoutStopSec=180",
            "LimitNOFILE=1048576",
            "StandardOutput=journal",
            "StandardError=journal",
            "",
            "[Install]",
            "WantedBy=multi-user.target",
            "",
        ]
    )


def _verify_benchmark_mode(service_text: str) -> list[str]:
    required = [
        "--max-model-len 131072",
        "--gpu-memory-utilization 0.80",
        "--max-num-seqs 2",
        "--max-num-batched-tokens 8192",
        "--enable-chunked-prefill",
    ]
    missing = [flag for flag in required if flag not in service_text]
    if "--enable-prefix-caching" in service_text:
        missing.append("unexpected --enable-prefix-caching")
    return missing


def _wait_for_remote_health(*, host: str, ssh_key: Path, port: int, timeout_seconds: int = 1800) -> None:
    started = time.time()
    while time.time() - started < timeout_seconds:
        proc = _run_ssh(
            host=host,
            ssh_key=ssh_key,
            remote_args=["bash", "-lc", f"curl -fsS http://127.0.0.1:{port}/health >/dev/null"],
            check=False,
        )
        if proc.returncode == 0:
            return
        time.sleep(5)
    raise TimeoutError(f"Timed out waiting for remote /health on port {port}")


def _start_tunnel(*, host: str, ssh_key: Path, local_port: int, remote_port: int, stderr_path: Path) -> subprocess.Popen[str]:
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_fh = stderr_path.open("a", encoding="utf-8")
    proc = subprocess.Popen(
        [
            "ssh",
            "-i",
            str(ssh_key),
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "ExitOnForwardFailure=yes",
            "-o",
            "ServerAliveInterval=60",
            "-o",
            "ServerAliveCountMax=30",
            "-N",
            "-L",
            f"127.0.0.1:{local_port}:127.0.0.1:{remote_port}",
            f"root@{host}",
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=stderr_fh,
        text=True,
        shell=False,
    )
    time.sleep(2)
    if proc.poll() is not None:
        stderr_fh.close()
        raise RuntimeError(f"SSH tunnel failed immediately. See {stderr_path}")
    proc._stderr_handle = stderr_fh  # type: ignore[attr-defined]
    return proc


def _stop_process(proc: subprocess.Popen[str] | None) -> None:
    if proc is None:
        return
    try:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=10)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    finally:
        stderr_fh = getattr(proc, "_stderr_handle", None)
        if stderr_fh is not None:
            stderr_fh.close()


def _preflight_endpoint(*, base_url: str, api_key: str, model_id: str) -> None:
    headers = {"Authorization": f"Bearer {api_key}"}
    with httpx.Client(timeout=30.0) as client:
        health = client.get(f"{base_url}/health", headers=headers)
        health.raise_for_status()

        models = client.get(f"{base_url}/v1/models", headers=headers)
        models.raise_for_status()
        model_ids = [str(item.get("id", "")) for item in models.json().get("data", [])]
        if model_id not in model_ids:
            raise RuntimeError(f"Expected {model_id!r} in /v1/models, got {model_ids}")

        response = client.post(
            f"{base_url}/v1/responses",
            headers=headers,
            json={
                "model": model_id,
                "input": "Reply with OK only.",
                "max_output_tokens": 16,
            },
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("output"):
            raise RuntimeError("Preflight /v1/responses returned no output")


def _build_benchmark_env(*, base_url: str, api_key: str, model_id: str) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["HARNESS_OPENROUTER_BASE_URL"] = base_url
    env["HARNESS_OPENROUTER_MODEL"] = model_id
    env["HARNESS_OPENROUTER_API_KEY"] = api_key
    env["OPENROUTER_BASE_URL"] = base_url
    env["OPENROUTER_MODEL"] = model_id
    env["OPENROUTER_API_KEY"] = api_key
    env["BENCH_OPENAI_BASE_URL"] = base_url
    env["BENCH_ANTHROPIC_BASE_URL"] = _trim_v1(base_url)
    env["BENCH_CODEX_MODEL"] = model_id
    env["BENCH_CLAUDE_MODEL"] = model_id
    env["BENCH_QWEN_MODEL"] = model_id
    env["BENCH_OPENCODE_MODEL"] = model_id
    env["BENCH_CODEX_CLI"] = str(REPO_ROOT / "codexopen.cmd")
    env["BENCH_CLAUDE_CLI"] = str(REPO_ROOT / "claudeopen.cmd")
    env["BENCH_QWEN_CLI"] = str(REPO_ROOT / "qwen.cmd")
    env["BENCH_OPENCODE_CLI"] = str(REPO_ROOT / "opencode.cmd")
    return env


def _run_named_suite(
    *,
    harness: str,
    suite_id: str,
    task_ids: list[str] | None,
    run_label: str,
    ledger_path: Path,
    timeout_s: int,
    eval_timeout_s: int,
    env: dict[str, str],
    logger: JobLogger,
) -> Path:
    cmd = [
        sys.executable,
        "run_named_suite.py",
        "--harness",
        harness,
        "--suites",
        suite_id,
        "--timeout-s",
        str(timeout_s),
        "--eval-timeout-s",
        str(eval_timeout_s),
        "--run-label",
        run_label,
        "--ledger",
        str(ledger_path),
    ]
    if task_ids:
        cmd.extend(["--task-ids", ",".join(task_ids)])
    proc = _run_local(cmd, cwd=BENCH_DIR, env=env, check=False)
    if proc.stdout.strip():
        logger.write(proc.stdout.rstrip())
    if proc.stderr.strip():
        logger.write(proc.stderr.rstrip())
    if proc.returncode != 0:
        raise RuntimeError(f"{harness} {suite_id} runner failed with exit code {proc.returncode}")
    payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    return Path(payload["runs"][0]["results_path"])


def _read_task_stderr(results_path: Path, harness: str) -> list[str]:
    raw_dir = results_path.parent / "raw" / harness
    if not raw_dir.exists():
        return []
    return [path.read_text(encoding="utf-8", errors="replace") for path in sorted(raw_dir.glob("*.stderr.txt"))]


def _smoke_has_operational_failure(results_path: Path) -> tuple[bool, list[str]]:
    payload = json.loads(results_path.read_text(encoding="utf-8"))
    results = payload.get("results", [])
    harness = str(payload.get("config", {}).get("harness", ""))
    reasons: list[str] = []

    nonzero = [record for record in results if int(record.get("exit_code", 0)) != 0]
    if nonzero:
        reasons.append(f"{len(nonzero)} task(s) exited non-zero during smoke run")

    stderr_text = "\n".join(_read_task_stderr(results_path, harness))
    for pattern in SMOKE_FAILURE_PATTERNS:
        if pattern.search(stderr_text):
            reasons.append(f"stderr matched {pattern.pattern!r}")
            break

    format_like = 0
    for record in results:
        joined_errors = " ".join(str(err) for err in record.get("errors", []))
        if any(pattern.search(joined_errors) for pattern in FORMAT_FAILURE_PATTERNS):
            format_like += 1
    if results and format_like >= max(3, len(results) // 2):
        reasons.append(f"{format_like}/{len(results)} tasks showed repeated parse/output-format failures")

    return bool(reasons), reasons


def _clear_opencode_state(level: int) -> None:
    root = Path.home() / ".opencode-openrouter"
    targets = [root] if level >= 2 else [root / "cache", root / "state"]
    for path in targets:
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)


def _restore_remote_service(
    *,
    host: str,
    ssh_key: Path,
    service_path: str,
    service_text: str,
    env_path: str,
    env_text: str,
    port: int,
    logger: JobLogger,
) -> None:
    logger.write("Restoring original remote vLLM service and env file")
    _write_remote_text(host=host, ssh_key=ssh_key, remote_path=env_path, content=env_text)
    _write_remote_text(host=host, ssh_key=ssh_key, remote_path=service_path, content=service_text)
    _run_ssh(host=host, ssh_key=ssh_key, remote_args=["systemctl", "daemon-reload"])
    _run_ssh(host=host, ssh_key=ssh_key, remote_args=["systemctl", "restart", "vllm.service"])
    _wait_for_remote_health(host=host, ssh_key=ssh_key, port=port)
    logger.write("Original interactive service is healthy again")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the DO H200 extreme100 benchmark matrix against a local GPU tunnel.")
    parser.add_argument("--droplet-ip", default="", help="Override droplet IP. Defaults to .do_state.json last_droplet.ip.")
    parser.add_argument("--ssh-key", default=str(DEFAULT_SSH_KEY))
    parser.add_argument("--suite-id", default="extreme100")
    parser.add_argument("--smoke-count", type=int, default=10)
    parser.add_argument("--timeout-s", type=int, default=1200)
    parser.add_argument("--eval-timeout-s", type=int, default=20)
    parser.add_argument("--local-port", type=int, default=DEFAULT_LOCAL_PORT)
    parser.add_argument("--remote-port", type=int, default=DEFAULT_REMOTE_PORT)
    parser.add_argument("--service-path", default=DEFAULT_SERVICE_PATH)
    parser.add_argument("--env-path", default=DEFAULT_ENV_PATH)
    parser.add_argument("--restore-interactive", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--dry-run", action="store_true", help="Render artifacts and inspect remote state without changing the server.")
    args = parser.parse_args()

    job_ts = time.strftime("%Y%m%d_%H%M%S")
    job_dir = JOB_RUNS_DIR / f"do-h200-gpt-oss-120b-{job_ts}"
    backups_dir = job_dir / "backups"
    ledgers_dir = job_dir / "ledgers"
    logger = JobLogger(job_dir / "orchestrator.log")

    tunnel_proc: subprocess.Popen[str] | None = None
    original_service_text = ""
    original_env_text = ""
    remote_env: dict[str, str] = {}
    remote_changed = False
    host = args.droplet_ip.strip() or _load_last_droplet_ip(DO_STATE_PATH)
    ssh_key = Path(args.ssh_key).expanduser().resolve()
    smoke_task_ids = _smoke_task_ids(args.suite_id, args.smoke_count)

    try:
        logger.write(f"Using droplet {host}")
        logger.write(f"Smoke task IDs: {', '.join(smoke_task_ids)}")

        original_service_text = _run_ssh(
            host=host,
            ssh_key=ssh_key,
            remote_args=["bash", "-lc", f"cat {args.service_path}"],
        ).stdout
        original_env_text = _run_ssh(
            host=host,
            ssh_key=ssh_key,
            remote_args=["bash", "-lc", f"cat {args.env_path}"],
        ).stdout
        remote_env = _parse_env_text(original_env_text)

        backups_dir.mkdir(parents=True, exist_ok=True)
        (backups_dir / "vllm.service.original").write_text(original_service_text, encoding="utf-8")
        (backups_dir / "gpt-oss-120b.env.original").write_text(original_env_text, encoding="utf-8")

        benchmark_service_text = _render_benchmark_service(args.env_path)
        (backups_dir / "vllm.service.benchmark").write_text(benchmark_service_text, encoding="utf-8")
        missing_flags = _verify_benchmark_mode(benchmark_service_text)
        if missing_flags:
            raise RuntimeError(f"Benchmark service render failed verification: {missing_flags}")

        if args.dry_run:
            logger.write("Dry run only. Saved original and benchmark service files locally.")
            return 0

        _run_ssh(
            host=host,
            ssh_key=ssh_key,
            remote_args=[
                "bash",
                "-lc",
                f"cp {args.service_path} {args.service_path}.bak-{job_ts} && cp {args.env_path} {args.env_path}.bak-{job_ts}",
            ],
        )
        _write_remote_text(host=host, ssh_key=ssh_key, remote_path=args.service_path, content=benchmark_service_text)
        remote_changed = True
        _run_ssh(host=host, ssh_key=ssh_key, remote_args=["systemctl", "daemon-reload"])
        _run_ssh(host=host, ssh_key=ssh_key, remote_args=["systemctl", "restart", "vllm.service"])
        _wait_for_remote_health(host=host, ssh_key=ssh_key, port=args.remote_port)

        active_service = _run_ssh(
            host=host,
            ssh_key=ssh_key,
            remote_args=["systemctl", "cat", "vllm.service"],
        ).stdout
        missing_flags = _verify_benchmark_mode(active_service)
        if missing_flags:
            raise RuntimeError(f"Live benchmark service missing expected flags: {missing_flags}")

        tunnel_proc = _start_tunnel(
            host=host,
            ssh_key=ssh_key,
            local_port=args.local_port,
            remote_port=args.remote_port,
            stderr_path=job_dir / "ssh-tunnel.stderr.log",
        )
        local_base_url = f"http://127.0.0.1:{args.local_port}"
        api_key = remote_env["VLLM_API_KEY"]
        served_model_name = remote_env["SERVED_MODEL_NAME"]
        _preflight_endpoint(base_url=local_base_url, api_key=api_key, model_id=served_model_name)
        logger.write("Endpoint preflight passed: /health, /v1/models, /v1/responses")

        benchmark_env = _build_benchmark_env(
            base_url=f"{local_base_url}/v1",
            api_key=api_key,
            model_id=served_model_name,
        )

        for harness in HARNESS_SEQUENCE:
            logger.write(f"Starting {harness} smoke10")
            smoke_ledger = ledgers_dir / f"{harness}_smoke10.json"
            smoke_results = _run_named_suite(
                harness=harness,
                suite_id=args.suite_id,
                task_ids=smoke_task_ids,
                run_label="do-h200-localgpu-smoke10",
                ledger_path=smoke_ledger,
                timeout_s=args.timeout_s,
                eval_timeout_s=args.eval_timeout_s,
                env=benchmark_env,
                logger=logger,
            )
            failed, reasons = _smoke_has_operational_failure(smoke_results)
            if failed:
                logger.write(f"Skipping full {harness} run due to smoke failure: {'; '.join(reasons)}")
                continue
            logger.write(f"Smoke passed for {harness}; starting full {args.suite_id}")
            _run_named_suite(
                harness=harness,
                suite_id=args.suite_id,
                task_ids=None,
                run_label="do-h200-localgpu-full",
                ledger_path=ledgers_dir / f"{harness}_full.json",
                timeout_s=args.timeout_s,
                eval_timeout_s=args.eval_timeout_s,
                env=benchmark_env,
                logger=logger,
            )

        logger.write("Starting opencode smoke10")
        opencode_smoke = _run_named_suite(
            harness=OPTIONAL_HARNESS,
            suite_id=args.suite_id,
            task_ids=smoke_task_ids,
            run_label="do-h200-localgpu-smoke10",
            ledger_path=ledgers_dir / "opencode_smoke10_attempt0.json",
            timeout_s=args.timeout_s,
            eval_timeout_s=args.eval_timeout_s,
            env=benchmark_env,
            logger=logger,
        )
        opencode_failed, reasons = _smoke_has_operational_failure(opencode_smoke)
        attempt = 0
        while opencode_failed and attempt < 2:
            attempt += 1
            _clear_opencode_state(level=attempt)
            logger.write(f"Retrying opencode smoke after local repair attempt {attempt}")
            opencode_smoke = _run_named_suite(
                harness=OPTIONAL_HARNESS,
                suite_id=args.suite_id,
                task_ids=smoke_task_ids,
                run_label=f"do-h200-localgpu-smoke10-fix{attempt}",
                ledger_path=ledgers_dir / f"opencode_smoke10_attempt{attempt}.json",
                timeout_s=args.timeout_s,
                eval_timeout_s=args.eval_timeout_s,
                env=benchmark_env,
                logger=logger,
            )
            opencode_failed, reasons = _smoke_has_operational_failure(opencode_smoke)

        if opencode_failed:
            logger.write(f"Opencode remained smoke-failing after two repair attempts: {'; '.join(reasons)}")
        else:
            logger.write("Opencode smoke passed; starting full extreme100")
            _run_named_suite(
                harness=OPTIONAL_HARNESS,
                suite_id=args.suite_id,
                task_ids=None,
                run_label="do-h200-localgpu-full",
                ledger_path=ledgers_dir / "opencode_full.json",
                timeout_s=args.timeout_s,
                eval_timeout_s=args.eval_timeout_s,
                env=benchmark_env,
                logger=logger,
            )

        return 0
    finally:
        _stop_process(tunnel_proc)
        if args.restore_interactive and remote_changed and original_service_text and original_env_text:
            try:
                restore_port = int(remote_env.get("PORT", str(args.remote_port)))
                _restore_remote_service(
                    host=host,
                    ssh_key=ssh_key,
                    service_path=args.service_path,
                    service_text=original_service_text,
                    env_path=args.env_path,
                    env_text=original_env_text,
                    port=restore_port,
                    logger=logger,
                )
            except Exception as exc:  # pragma: no cover - remote safety path
                logger.write(f"Restore failed: {exc}")
        logger.close()


if __name__ == "__main__":
    raise SystemExit(main())
