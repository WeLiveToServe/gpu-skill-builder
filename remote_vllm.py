"""
remote_vllm.py — SSH-based vLLM deployment for raw GPU VMs.

Given a running VM's IP and SSH key, installs the target model under
systemd and returns an OpenAI-compatible endpoint URL.

Currently called by do_provider for DigitalOcean droplets.
Requires on the remote VM: vLLM pre-installed, systemd, Python 3, curl.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import re
import shlex
from pathlib import Path

from models import Provider
from profile_registry import DeploymentProfile, ModelProfile

logger = logging.getLogger(__name__)

_DEFAULT_PORT = 8000
DEFAULT_VLLM_PORT = _DEFAULT_PORT
_DEFAULT_GPU_MEM_UTIL = 0.92
_DEFAULT_HEALTH_TIMEOUT_SEC = 1800  # 30 min — large models take a while

_REMOTE_SCRIPT = """\
set -euo pipefail

SERVICE_B64="$1"
MODEL_ID="$2"
SERVED_MODEL_NAME="$3"
PORT="$4"
HEALTH_TIMEOUT="$5"
HF_TOKEN="${HF_TOKEN:-}"
export MODEL_ID PORT SERVED_MODEL_NAME SERVICE_B64
SERVICE_FILE='/etc/systemd/system/vllm.service'

echo '[1/6] ensuring runtime compatibility'
if echo "$MODEL_ID" | grep -qi 'gemma-4'; then
  tf_major=$(python3 -c "import transformers; print(int(transformers.__version__.split('.')[0]))")
  if [ "$tf_major" -lt 5 ]; then
    echo 'upgrading transformers/accelerate for gemma-4 support'
    python3 -m pip install --no-input --upgrade "transformers>=5,<6" "huggingface-hub>=1,<2" accelerate
  else
    echo "transformers major version $tf_major is compatible"
  fi
fi

echo '[2/6] stopping existing vLLM processes'
systemctl stop vllm.service >/dev/null 2>&1 || true

if ss -ltnp | grep -q ":$PORT "; then
  pids=$(ss -ltnp | awk -v p=":$PORT" '$0 ~ p {print $NF}' | sed -E 's/.*pid=([0-9]+).*/\\1/' | sort -u)
  if [ -n "$pids" ]; then
    kill -TERM $pids || true
    sleep 3
    kill -KILL $pids || true
  fi
fi
pkill -f "vllm serve" || true
sleep 2

echo '[3/6] writing systemd unit'
python3 - <<'PY'
import base64
import os
from pathlib import Path

content = base64.b64decode(os.environ["SERVICE_B64"]).decode("utf-8")
hf_token = os.environ.get("HF_TOKEN", "")
hf_lines = ""
if hf_token:
    hf_lines = (
        f"Environment=HF_TOKEN={hf_token}\\n"
        f"Environment=HUGGING_FACE_HUB_TOKEN={hf_token}\\n"
    )
content = content.replace("__HF_ENV_LINES__\\n", hf_lines)
Path("/etc/systemd/system/vllm.service").write_text(content, encoding="utf-8")
PY

echo '[4/6] reloading + starting service'
systemctl daemon-reload
systemctl enable vllm.service >/dev/null 2>&1 || true
systemctl restart vllm.service

echo '[5/6] waiting for /health (up to $HEALTH_TIMEOUT seconds)'
for i in $(seq 1 "$HEALTH_TIMEOUT"); do
  if curl -fsS "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
    echo "health_ok_seconds=$i"
    break
  fi
  if ! systemctl --quiet is-active vllm.service; then
    echo 'service_failed_before_health'
    systemctl --no-pager --full status vllm.service | sed -n '1,80p'
    journalctl -u vllm.service -n 120 --no-pager
    exit 1
  fi
  sleep 1
  if [ "$i" -eq "$HEALTH_TIMEOUT" ]; then
    echo 'health_timeout'
    systemctl --no-pager --full status vllm.service | sed -n '1,80p'
    exit 1
  fi
done

echo '[6/6] validating /v1/models'
python3 - <<'VLLMPY'
import json, urllib.request
import os
model = os.environ['SERVED_MODEL_NAME']
port = os.environ['PORT']
url = f'http://127.0.0.1:{port}/v1/models'
payload = json.loads(urllib.request.urlopen(url, timeout=15).read().decode())
ids = [x.get('id', '') for x in payload.get('data', [])]
print('served_models=', ids)
assert model in ids, f'Expected {model!r} not in /v1/models: {ids}'
print('MODEL_SWAP_OK')
VLLMPY
"""


def _validate_model_id(model_id: str) -> None:
    if not model_id:
        raise ValueError("model_id must not be empty.")
    if not re.match(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$", model_id):
        raise ValueError(
            "model_id must contain only letters, digits, '.', '_', '-', and '/', "
            "and must start with an alphanumeric character."
        )
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in model_id):
        raise ValueError("model_id contains control characters.")


def _validate_token(token: str, field_name: str) -> None:
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in token):
        raise ValueError(f"{field_name} contains control characters.")
    if any(ch.isspace() for ch in token):
        raise ValueError(f"{field_name} must not contain whitespace.")


def _quote_args(args: list[str]) -> str:
    return " ".join(shlex.quote(arg) for arg in args)


def render_vllm_command_args(
    *,
    model_profile: ModelProfile,
    deployment_profile: DeploymentProfile,
) -> list[str]:
    runtime = deployment_profile.runtime
    served_model_name = deployment_profile.served_model_name or model_profile.provider_model_id
    args = [
        "/usr/local/bin/vllm",
        "serve",
        model_profile.provider_model_id,
        "--host",
        "0.0.0.0",
        "--port",
        str(runtime.port),
        "--served-model-name",
        served_model_name,
        "--generation-config",
        "vllm",
        "--max-model-len",
        str(runtime.max_model_len),
        "--gpu-memory-utilization",
        f"{runtime.gpu_memory_utilization:.2f}",
        "--tensor-parallel-size",
        str(runtime.tensor_parallel_size),
        "--pipeline-parallel-size",
        str(runtime.pipeline_parallel_size),
        "--max-num-seqs",
        str(runtime.max_num_seqs),
        "--max-num-batched-tokens",
        str(runtime.max_num_batched_tokens),
    ]
    if runtime.kv_cache_dtype:
        args.extend(["--kv-cache-dtype", runtime.kv_cache_dtype])
    if runtime.expert_parallel:
        args.append("--enable-expert-parallel")
    if runtime.enable_eplb:
        args.append("--enable-eplb")
    if runtime.prefix_caching_policy == "enabled":
        args.append("--enable-prefix-caching")
    if runtime.chunked_prefill_policy == "enabled":
        args.append("--enable-chunked-prefill")
    args.extend(runtime.extra_args)
    return args


def render_vllm_service_unit(
    *,
    model_profile: ModelProfile,
    deployment_profile: DeploymentProfile,
) -> str:
    served_model_name = deployment_profile.served_model_name or model_profile.provider_model_id
    command = _quote_args(
        render_vllm_command_args(
            model_profile=model_profile,
            deployment_profile=deployment_profile,
        )
    )
    return "\n".join(
        [
            "[Unit]",
            f"Description=vLLM OpenAI-compatible server ({served_model_name})",
            "After=network.target",
            "",
            "[Service]",
            "Type=simple",
            "User=root",
            "WorkingDirectory=/root",
            "__HF_ENV_LINES__",
            f"ExecStart={command}",
            "Restart=on-failure",
            "RestartSec=10",
            "TimeoutStopSec=180",
            "StandardOutput=journal",
            "StandardError=journal",
            "",
            "[Install]",
            "WantedBy=multi-user.target",
            "",
        ]
    )


def _default_model_profile(model_id: str) -> ModelProfile:
    return ModelProfile(
        id=f"legacy-{model_id.split('/')[-1].lower().replace('.', '-')}",
        provider_model_id=model_id,
        runtime_family="vllm",
        default_alias=model_id.split("/")[-1],
        throughput_hint="legacy fallback",
    )


def _default_deployment_profile(
    *,
    model_profile: ModelProfile,
    port: int,
    gpu_memory_utilization: float,
    health_timeout_sec: int,
) -> DeploymentProfile:
    return DeploymentProfile(
        id="legacy-remote-vllm-default",
        model_profile_id=model_profile.id,
        provider=Provider.DIGITALOCEAN,
        hardware_slug="*",
        runtime_kind="vllm",
        endpoint_class="openai-compatible",
        managed_by_provider=False,
        served_model_name=model_profile.provider_model_id,
        description="legacy compatibility deployment profile",
        runtime={
            "port": port,
            "max_model_len": 32768,
            "max_num_seqs": 4,
            "gpu_memory_utilization": gpu_memory_utilization,
            "max_num_batched_tokens": 8192,
            "tensor_parallel_size": 1,
            "pipeline_parallel_size": 1,
            "prefix_caching_policy": "enabled",
            "chunked_prefill_policy": "enabled",
        },
        readiness={"health_timeout_seconds": health_timeout_sec},
    )


async def deploy_vllm_remote(
    ip: str,
    model_id: str,
    ssh_key_path: str | Path,
    port: int = _DEFAULT_PORT,
    gpu_memory_utilization: float = _DEFAULT_GPU_MEM_UTIL,
    health_timeout_sec: int = _DEFAULT_HEALTH_TIMEOUT_SEC,
    hf_token: str | None = None,
    deployment_profile: DeploymentProfile | None = None,
    model_profile: ModelProfile | None = None,
) -> str:
    """
    SSH into a running VM, load model_id under systemd vllm.service,
    wait for the health probe, and return the OpenAI-compatible endpoint URL.

    Returns: "http://<ip>:<port>"
    Raises: RuntimeError on SSH failure, service crash, health timeout, or model mismatch.
    """
    _validate_model_id(model_id)
    if hf_token:
        _validate_token(hf_token, "hf_token")

    resolved_model_profile = model_profile or _default_model_profile(model_id)
    resolved_deployment_profile = deployment_profile or _default_deployment_profile(
        model_profile=resolved_model_profile,
        port=port,
        gpu_memory_utilization=gpu_memory_utilization,
        health_timeout_sec=health_timeout_sec,
    )
    rendered_service = render_vllm_service_unit(
        model_profile=resolved_model_profile,
        deployment_profile=resolved_deployment_profile,
    )
    service_b64 = base64.b64encode(rendered_service.encode("utf-8")).decode("ascii")
    served_model_name = resolved_deployment_profile.served_model_name or resolved_model_profile.provider_model_id
    runtime = resolved_deployment_profile.runtime
    timeout_seconds = resolved_deployment_profile.readiness.health_timeout_seconds

    logger.info(
        "deploy_vllm_remote: %s  model=%s  profile=%s  port=%d  gpu_util=%.2f  timeout=%ds",
        ip,
        model_id,
        resolved_deployment_profile.id,
        runtime.port,
        runtime.gpu_memory_utilization,
        timeout_seconds,
    )
    logger.info("  SSH key: %s", ssh_key_path)
    logger.info("  Model load may take several minutes — standing by...")

    remote_cmd: list[str] = []
    if hf_token:
        remote_cmd.extend(["env", f"HF_TOKEN={hf_token}", f"HUGGING_FACE_HUB_TOKEN={hf_token}"])
    remote_cmd.extend(
        [
            "bash",
            "-s",
            "--",
            service_b64,
            model_id,
            served_model_name,
            str(runtime.port),
            str(timeout_seconds),
        ]
    )

    proc = await asyncio.create_subprocess_exec(
        "ssh",
        "-i",
        str(ssh_key_path),
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "ConnectTimeout=30",
        "-o",
        "ServerAliveInterval=60",
        "-o",
        "ServerAliveCountMax=30",
        f"root@{ip}",
        *remote_cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    stdout, _ = await proc.communicate(input=_REMOTE_SCRIPT.encode())
    output = stdout.decode(errors="replace")

    for line in output.splitlines():
        logger.info("  [remote] %s", line)

    if "MODEL_SWAP_OK" not in output:
        raise RuntimeError(
            f"vLLM deploy failed on {ip} for model {model_id!r}.\n"
            f"SSH exit code: {proc.returncode}\n"
            f"Remote output (last 40 lines):\n"
            + "\n".join(output.splitlines()[-40:])
        )

    endpoint_url = f"http://{ip}:{runtime.port}"
    logger.info("deploy_vllm_remote: endpoint ready — %s", endpoint_url)
    return endpoint_url
