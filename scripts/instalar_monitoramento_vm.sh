#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_USER="${SUDO_USER:-$(stat -c '%U' "$APP_DIR")}" 
RUN_GROUP="$(id -gn "$RUN_USER")"
STATE_DIR="/var/lib/mei-mg-email"
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
render_unit "$APP_DIR/deploy/systemd/mei-mg-email-brevo-reconciler.service" "/etc/systemd/system/mei-mg-email-brevo-reconciler.service"
render_unit "$APP_DIR/deploy/systemd/mei-mg-email-worker.service" "/etc/systemd/system/mei-mg-email-worker.service"

# Estado operacional persistente fica fora do Git. Se um deploy antigo ainda
# tiver o sentinel como arquivo regular no repo, preserve seu conteudo antes de
# substitui-lo pelo link para /var/lib.
"${SUDO[@]}" install -d -m 0750 -o "$RUN_USER" -g "$RUN_GROUP" "$STATE_DIR"
mkdir -p "$APP_DIR/runtime/monitor"
chown "$RUN_USER":"$RUN_GROUP" "$APP_DIR/runtime/monitor" 2>/dev/null || true
if [[ -f "$APP_DIR/runtime/sender_blocked.pause" && ! -L "$APP_DIR/runtime/sender_blocked.pause" ]]; then
  "${SUDO[@]}" cp -f "$APP_DIR/runtime/sender_blocked.pause" "$STATE_DIR/sender_blocked.pause"
  "${SUDO[@]}" chown "$RUN_USER":"$RUN_GROUP" "$STATE_DIR/sender_blocked.pause"
  "${SUDO[@]}" chmod 0640 "$STATE_DIR/sender_blocked.pause"
fi
rm -f "$APP_DIR/runtime/sender_blocked.pause"

"${SUDO[@]}" systemctl daemon-reload
"${SUDO[@]}" systemctl enable --now mei-mg-email-base-sync.timer
"${SUDO[@]}" systemctl enable --now mei-mg-email-monitor.service
"${SUDO[@]}" systemctl enable --now mei-mg-email-worker.service
if "${SUDO[@]}" systemctl cat mei-mg-email-ndr-guard.service >/dev/null 2>&1; then
  "${SUDO[@]}" systemctl disable --now mei-mg-email-ndr-guard.service
fi
"${SUDO[@]}" systemctl enable --now mei-mg-email-brevo-reconciler.service

# Executa uma sincronizacao imediatamente para validar a cadeia completa em vez
# de esperar o proximo horario do timer. Falha aqui e tratada como falha de instalacao.
if ! "${SUDO[@]}" systemctl start mei-mg-email-base-sync.service; then
  echo "ERRO: sincronizacao inicial da base falhou" >&2
  "${SUDO[@]}" journalctl -u mei-mg-email-base-sync.service -n 80 --no-pager || true
  exit 2
fi

"${SUDO[@]}" systemctl restart mei-mg-email-monitor.service
"${SUDO[@]}" systemctl restart mei-mg-email-brevo-reconciler.service

echo "MONITORAMENTO_VM_INSTALADO"
echo "app_dir=$APP_DIR"
echo "run_user=$RUN_USER"
echo "python=$PYTHON"
echo "state_dir=$STATE_DIR"
"${SUDO[@]}" systemctl is-active mei-mg-email-monitor.service
"${SUDO[@]}" systemctl is-active mei-mg-email-worker.service
"${SUDO[@]}" systemctl is-active mei-mg-email-brevo-reconciler.service
"${SUDO[@]}" systemctl is-active mei-mg-email-base-sync.timer
"${SUDO[@]}" systemctl is-enabled mei-mg-email-brevo-reconciler.service
"${SUDO[@]}" systemctl is-enabled mei-mg-email-base-sync.timer
"${SUDO[@]}" systemctl list-timers mei-mg-email-base-sync.timer --no-pager
