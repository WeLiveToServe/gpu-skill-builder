param(
    [string]$HostIp = "",
    [string]$ModelId = "google/gemma-4-31B-it",
    [string]$SshKeyPath = "$HOME\.ssh\do_agent_ed25519",
    [int]$Port = 8000,
    [double]$GpuMemoryUtilization = 0.92,
    [int]$HealthTimeoutSec = 1800
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-HostIp {
    param([string]$RequestedIp)
    if ($RequestedIp) {
        return $RequestedIp
    }

    $statePath = Join-Path $PSScriptRoot "..\..\.do_state.json"
    if (Test-Path $statePath) {
        try {
            $state = Get-Content $statePath -Raw | ConvertFrom-Json
            if ($state.last_droplet.ip) {
                return [string]$state.last_droplet.ip
            }
        }
        catch {
            Write-Warning "Could not parse .do_state.json: $($_.Exception.Message)"
        }
    }

    throw "HostIp not provided and no IP found in .do_state.json."
}

if (-not (Test-Path $SshKeyPath)) {
    throw "SSH key not found: $SshKeyPath"
}

$resolvedIp = Resolve-HostIp -RequestedIp $HostIp
$gpuUtilText = "{0:0.##}" -f $GpuMemoryUtilization

Write-Host "Target droplet : $resolvedIp"
Write-Host "Target model   : $ModelId"
Write-Host "API port       : $Port"
Write-Host "GPU mem util   : $gpuUtilText"
Write-Host "Health timeout : $HealthTimeoutSec sec"
Write-Host ""

$remoteScriptTemplate = @'
set -euo pipefail

MODEL_ID='__MODEL_ID__'
PORT='__PORT__'
GPU_UTIL='__GPU_UTIL__'
HEALTH_TIMEOUT='__HEALTH_TIMEOUT__'
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
  pids=$(ss -ltnp | awk -v p=":$PORT" '$0 ~ p {print $NF}' | sed -E 's/.*pid=([0-9]+).*/\1/' | sort -u)
  if [ -n "$pids" ]; then
    kill -TERM $pids || true
    sleep 3
    kill -KILL $pids || true
  fi
fi
pkill -f "vllm serve" || true
sleep 2

echo '[3/6] writing systemd unit'
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=vLLM OpenAI-compatible server ($MODEL_ID)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root
ExecStart=/usr/local/bin/vllm serve $MODEL_ID --host 0.0.0.0 --port $PORT --gpu-memory-utilization $GPU_UTIL --enable-prefix-caching --served-model-name $MODEL_ID
Restart=on-failure
RestartSec=10
TimeoutStopSec=180
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo '[4/6] reloading + starting service'
systemctl daemon-reload
systemctl enable vllm.service >/dev/null 2>&1 || true
systemctl restart vllm.service

echo '[5/6] waiting for /health'
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
python3 -c "import json,sys,urllib.request; model='__MODEL_ID__'; port='__PORT__'; url=f'http://127.0.0.1:{port}/v1/models'; payload=json.loads(urllib.request.urlopen(url, timeout=15).read().decode('utf-8')); ids=[x.get('id','') for x in payload.get('data',[])]; print('served_models=', ids); assert model in ids, f\"Expected model {model!r} not found in /v1/models\"; print('MODEL_SWAP_OK')"
'@

$remoteScript = $remoteScriptTemplate.Replace("__MODEL_ID__", $ModelId)
$remoteScript = $remoteScript.Replace("__PORT__", [string]$Port)
$remoteScript = $remoteScript.Replace("__GPU_UTIL__", $gpuUtilText)
$remoteScript = $remoteScript.Replace("__HEALTH_TIMEOUT__", [string]$HealthTimeoutSec)

$remoteScript | ssh -i $SshKeyPath -o StrictHostKeyChecking=no root@$resolvedIp "bash -s"
