#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/home/ubuntu/mei-mg-email"
RUN_USER="ubuntu"
PYTHON="/home/ubuntu/mei-mg-email/.venv/bin/python"

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
sudo systemctl restart mei-mg-email-worker.service

echo "=== STATUS DOS SERVICOS ==="
sudo systemctl is-active mei-mg-email-worker.service
sudo systemctl is-active mei-mg-email-autorepair-15min.timer
sudo systemctl is-active mei-mg-email-monitor.service
sudo systemctl list-timers mei-mg-email-autorepair-15min.timer --no-pager
