"""
remote_vllm.py — SSH-based vLLM deployment for raw GPU VMs.

Given a running VM's IP and SSH key, installs the target model under
systemd and returns an OpenAI-compatible endpoint URL.

Currently called by do_provider for DigitalOcean droplets.
Requires on the remote VM: vLLM pre-installed, systemd, Python 3, curl.
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_PORT = 8000
DEFAULT_VLLM_PORT = _DEFAULT_PORT
_DEFAULT_GPU_MEM_UTIL = 0.92
_DEFAULT_HEALTH_TIMEOUT_SEC = 1800  # 30 min — large models take a while

_REMOTE_SCRIPT = """\
set -euo pipefail

MODEL_ID="$1"
PORT="$2"
GPU_UTIL="$3"
HEALTH_TIMEOUT="$4"
HF_TOKEN="${HF_TOKEN:-}"
export MODEL_ID PORT
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
{
  printf '[Unit]\\n'
  printf 'Description=vLLM OpenAI-compatible server (%s)\\n' "$MODEL_ID"
  printf 'After=network.target\\n\\n'
  printf '[Service]\\n'
  printf 'Type=simple\\n'
  printf 'User=root\\n'
  printf 'WorkingDirectory=/root\\n'
  if [ -n "$HF_TOKEN" ]; then
    printf 'Environment=HF_TOKEN=%s\\n' "$HF_TOKEN"
    printf 'Environment=HUGGING_FACE_HUB_TOKEN=%s\\n' "$HF_TOKEN"
  fi
  printf 'ExecStart=/usr/local/bin/vllm serve %s --host 0.0.0.0 --port %s --gpu-memory-utilization %s --enable-prefix-caching --served-model-name %s\\n' "$MODEL_ID" "$PORT" "$GPU_UTIL" "$MODEL_ID"
  printf 'Restart=on-failure\\n'
  printf 'RestartSec=10\\n'
  printf 'TimeoutStopSec=180\\n'
  printf 'StandardOutput=journal\\n'
  printf 'StandardError=journal\\n\\n'
  printf '[Install]\\n'
  printf 'WantedBy=multi-user.target\\n'
} > "$SERVICE_FILE"

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
model = os.environ['MODEL_ID']
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


async def deploy_vllm_remote(
    ip: str,
    model_id: str,
    ssh_key_path: str | Path,
    port: int = _DEFAULT_PORT,
    gpu_memory_utilization: float = _DEFAULT_GPU_MEM_UTIL,
    health_timeout_sec: int = _DEFAULT_HEALTH_TIMEOUT_SEC,
    hf_token: str | None = None,
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

    logger.info(
        "deploy_vllm_remote: %s  model=%s  port=%d  gpu_util=%.2f  timeout=%ds",
        ip, model_id, port, gpu_memory_utilization, health_timeout_sec,
    )
    logger.info("  SSH key: %s", ssh_key_path)
    logger.info("  Model load may take several minutes — standing by...")

    remote_cmd = []
    if hf_token:
        remote_cmd.extend(["env", f"HF_TOKEN={hf_token}", f"HUGGING_FACE_HUB_TOKEN={hf_token}"])
    remote_cmd.extend(
        [
            "bash",
            "-s",
            "--",
            model_id,
            str(port),
            f"{gpu_memory_utilization:.2f}",
            str(health_timeout_sec),
        ]
    )

    proc = await asyncio.create_subprocess_exec(
        "ssh",
        "-i", str(ssh_key_path),
        "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=30",
        "-o", "ServerAliveInterval=60",  # keepalive during long model load
        "-o", "ServerAliveCountMax=30",
        f"root@{ip}",
        *remote_cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,  # merge so log lines stay ordered
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

    endpoint_url = f"http://{ip}:{port}"
    logger.info("deploy_vllm_remote: endpoint ready — %s", endpoint_url)
    return endpoint_url
