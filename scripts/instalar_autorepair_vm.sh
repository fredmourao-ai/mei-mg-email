#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_USER="${SUDO_USER:-$(stat -c '%U' "$APP_DIR")}"
STATE_DIR="/var/lib/mei-mg-email"
if [[ -x "$APP_DIR/.venv/bin/python" ]]; then
  PYTHON="$APP_DIR/.venv/bin/python"
else
  PYTHON="$(command -v python3)"
fi

chmod +x "$APP_DIR/scripts/validar_e_reparar_envios_15min.py"

sed \
  -e "s|__APP_DIR__|$APP_DIR|g" \
  -e "s|__RUN_USER__|$RUN_USER|g" \
  -e "s|__PYTHON__|$PYTHON|g" \
  "$APP_DIR/deploy/systemd/mei-mg-email-autorepair-15min.service" | sudo tee /etc/systemd/system/mei-mg-email-autorepair-15min.service >/dev/null

sudo cp "$APP_DIR/deploy/systemd/mei-mg-email-autorepair-15min.timer" /etc/systemd/system/mei-mg-email-autorepair-15min.timer
sudo chmod 0644 /etc/systemd/system/mei-mg-email-autorepair-15min.*

sudo systemctl daemon-reload
sudo systemctl enable --now mei-mg-email-autorepair-15min.timer

echo "=== EXECUTANDO VALIDACAO E RECUPERACAO INICIAL ==="
"$PYTHON" "$APP_DIR/scripts/validar_e_reparar_envios_15min.py"

echo "=== REINICIANDO E HABILITANDO WORKER E MONITOR ==="
sudo systemctl enable --now mei-mg-email-monitor.service
sudo systemctl enable mei-mg-email-worker.service
if [[ -f "$STATE_DIR/sender_blocked.pause" ]]; then
  sudo systemctl stop mei-mg-email-worker.service
  echo "WORKER_MANTIDO_PARADO_POR_CIRCUIT_BREAKER"
else
  sudo systemctl restart mei-mg-email-worker.service
fi

echo "=== STATUS DOS SERVICOS ==="
if [[ -f "$STATE_DIR/sender_blocked.pause" ]]; then
  if sudo systemctl is-active --quiet mei-mg-email-worker.service; then
    echo "ERRO: worker ativo apesar do circuit breaker" >&2
    exit 3
  fi
  echo "mei-mg-email-worker.service=inactive_circuit_breaker"
else
  sudo systemctl is-active mei-mg-email-worker.service
fi
sudo systemctl is-active mei-mg-email-autorepair-15min.timer
sudo systemctl is-active mei-mg-email-monitor.service
sudo systemctl list-timers mei-mg-email-autorepair-15min.timer --no-pager
