#!/usr/bin/env bash
set -euo pipefail

# Installs and starts gpu monitor daemon as a systemd service on Linux.
#
# Usage:
#   sudo bash install_monitor_service.sh \
#     --repo-dir /opt/gpu-skill-builder \
#     --env-file /opt/gpu-skill-builder/.env

REPO_DIR="/opt/gpu-skill-builder"
ENV_FILE=""
SERVICE_NAME="gpu-monitor"
PYTHON_BIN="python3"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-dir)
      REPO_DIR="$2"
      shift 2
      ;;
    --env-file)
      ENV_FILE="$2"
      shift 2
      ;;
    --service-name)
      SERVICE_NAME="$2"
      shift 2
      ;;
    --python-bin)
      PYTHON_BIN="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

if [[ -z "$ENV_FILE" ]]; then
  ENV_FILE="${REPO_DIR}/.env"
fi

if [[ ! -d "$REPO_DIR" ]]; then
  echo "Repo dir does not exist: $REPO_DIR" >&2
  exit 1
fi
if [[ ! -f "${REPO_DIR}/gpu_monitor_daemon.py" ]]; then
  echo "gpu_monitor_daemon.py not found under ${REPO_DIR}" >&2
  exit 1
fi
if [[ ! -f "${REPO_DIR}/requirements.txt" ]]; then
  echo "requirements.txt not found under ${REPO_DIR}" >&2
  exit 1
fi
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Env file not found: $ENV_FILE" >&2
  exit 1
fi

sudo mkdir -p /opt/gpu-monitor
sudo chown -R "$(id -u):$(id -g)" /opt/gpu-monitor

VENV_DIR="/opt/gpu-monitor/venv"
${PYTHON_BIN} -m venv "$VENV_DIR"
"${VENV_DIR}/bin/pip" install --upgrade pip
"${VENV_DIR}/bin/pip" install -r "${REPO_DIR}/requirements.txt"

SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}.service"
sudo tee "$SERVICE_PATH" >/dev/null <<EOF
[Unit]
Description=GPU Fleet Monitor Daemon
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=${REPO_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${VENV_DIR}/bin/python ${REPO_DIR}/gpu_monitor_daemon.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now "${SERVICE_NAME}.service"

echo "Service installed and started: ${SERVICE_NAME}"
echo "Check status with: sudo systemctl status ${SERVICE_NAME}"
echo "Tail logs with: sudo journalctl -u ${SERVICE_NAME} -f"
