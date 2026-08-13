#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_DIR"

if [[ "$(id -u)" -eq 0 ]]; then
  SUDO=()
else
  SUDO=(sudo)
fi

RUN_USER="${SUDO_USER:-$(stat -c '%U' "$APP_DIR")}" 
RUN_GROUP="$(id -gn "$RUN_USER")"
STATE_DIR="/var/lib/mei-mg-email"
SENTINEL="$STATE_DIR/sender_blocked.pause"

# P0: abra a pausa persistente ANTES de migrations/restarts. Este release foi
# criado durante incidente AS(42004); nenhum passo abaixo autoriza retomada.
"${SUDO[@]}" install -d -m 0750 -o "$RUN_USER" -g "$RUN_GROUP" "$STATE_DIR"
cat <<'EOF' | "${SUDO[@]}" tee "$SENTINEL" >/dev/null
blocked_at_utc=2026-08-13T00:05:45+00:00
sender=naoresponda@dev.shopvivaliz.com.br
error=550 5.1.8 Access denied, bad outbound sender AS(42004)
source=deploy_hardening_20260813
resume_allowed=false
EOF
"${SUDO[@]}" chown "$RUN_USER":"$RUN_GROUP" "$SENTINEL"
"${SUDO[@]}" chmod 0640 "$SENTINEL"
echo "DEPLOY_PAUSE_ASSERTED path=$SENTINEL"

# Aplica somente migrations novas/pendentes. Flyway continua sendo a fonte de
# verdade; migrations existentes nao sao editadas.
docker compose run --rm flyway migrate

# Instala monitor, NDR guard, timer diario e migra o link do sentinel para /var/lib.
bash scripts/instalar_monitoramento_vm.sh

# Reinicia o worker somente depois que a pausa persistente existe. O processo
# pode ficar active, mas deve permanecer fail-closed sem chamar sendMail.
if systemctl list-unit-files mei-mg-email-worker.service --no-legend 2>/dev/null | grep -q 'mei-mg-email-worker.service'; then
  "${SUDO[@]}" systemctl restart mei-mg-email-worker.service
fi

# Atestado objetivo do rollout.
SHA="$(git rev-parse HEAD)"
echo "DEPLOY_SHA=$SHA"
test -f "$SENTINEL"
echo "DEPLOY_SENDER_PAUSED=true"
"${SUDO[@]}" systemctl is-active mei-mg-email-monitor.service
"${SUDO[@]}" systemctl is-active mei-mg-email-ndr-guard.service
"${SUDO[@]}" systemctl is-active mei-mg-email-base-sync.timer
"${SUDO[@]}" systemctl is-enabled mei-mg-email-ndr-guard.service
"${SUDO[@]}" systemctl is-enabled mei-mg-email-base-sync.timer

# Verifica que V022/V023/V024 constam como aplicadas no Flyway.
INFO="$(docker compose run --rm flyway info)"
printf '%s\n' "$INFO"
printf '%s\n' "$INFO" | grep -Eq '(^|[[:space:]])22([[:space:]]|\|).*Success|V022' || { echo 'ERRO: V022 nao confirmada' >&2; exit 22; }
printf '%s\n' "$INFO" | grep -Eq '(^|[[:space:]])23([[:space:]]|\|).*Success|V023' || { echo 'ERRO: V023 nao confirmada' >&2; exit 23; }
printf '%s\n' "$INFO" | grep -Eq '(^|[[:space:]])24([[:space:]]|\|).*Success|V024' || { echo 'ERRO: V024 nao confirmada' >&2; exit 24; }

echo "DEPLOY_HARDENING_OK"
echo "WORKER_RESUME_ALLOWED=false"
