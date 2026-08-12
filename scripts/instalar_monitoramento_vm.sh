#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_USER="${SUDO_USER:-$(stat -c '%U' "$APP_DIR")}" 
if [[ -x "$APP_DIR/.venv/bin/python" ]]; then
  PYTHON="$APP_DIR/.venv/bin/python"
else
  PYTHON="$(command -v python3)"
fi

if [[ -z "$PYTHON" ]]; then
  echo "ERRO: python3 nao encontrado" >&2
  exit 1
fi

if [[ "$(id -u)" -eq 0 ]]; then
  SUDO=()
else
  SUDO=(sudo)
fi

render_unit() {
  local src="$1"
  local dst="$2"
  local tmp
  tmp="$(mktemp)"
  sed \
    -e "s|__APP_DIR__|$APP_DIR|g" \
    -e "s|__RUN_USER__|$RUN_USER|g" \
    -e "s|__PYTHON__|$PYTHON|g" \
    "$src" > "$tmp"
  "${SUDO[@]}" install -m 0644 "$tmp" "$dst"
  rm -f "$tmp"
}

render_unit "$APP_DIR/deploy/systemd/mei-mg-email-monitor.service" "/etc/systemd/system/mei-mg-email-monitor.service"
render_unit "$APP_DIR/deploy/systemd/mei-mg-email-base-sync.service" "/etc/systemd/system/mei-mg-email-base-sync.service"
render_unit "$APP_DIR/deploy/systemd/mei-mg-email-base-sync.timer" "/etc/systemd/system/mei-mg-email-base-sync.timer"

mkdir -p "$APP_DIR/runtime/monitor"
chown "$RUN_USER":"$(id -gn "$RUN_USER")" "$APP_DIR/runtime/monitor" 2>/dev/null || true

"${SUDO[@]}" systemctl daemon-reload
"${SUDO[@]}" systemctl enable --now mei-mg-email-base-sync.timer
"${SUDO[@]}" systemctl enable --now mei-mg-email-monitor.service

# Executa uma sincronizacao imediatamente para validar a cadeia completa em vez
# de esperar o proximo horario do timer. Falha aqui e tratada como falha de instalacao.
if ! "${SUDO[@]}" systemctl start mei-mg-email-base-sync.service; then
  echo "ERRO: sincronizacao inicial da base falhou" >&2
  "${SUDO[@]}" journalctl -u mei-mg-email-base-sync.service -n 80 --no-pager || true
  exit 2
fi

"${SUDO[@]}" systemctl restart mei-mg-email-monitor.service

echo "MONITORAMENTO_VM_INSTALADO"
echo "app_dir=$APP_DIR"
echo "run_user=$RUN_USER"
echo "python=$PYTHON"
"${SUDO[@]}" systemctl is-active mei-mg-email-monitor.service
"${SUDO[@]}" systemctl is-active mei-mg-email-base-sync.timer
"${SUDO[@]}" systemctl is-enabled mei-mg-email-base-sync.timer
"${SUDO[@]}" systemctl list-timers mei-mg-email-base-sync.timer --no-pager
