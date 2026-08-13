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
WORKER_UNIT="mei-mg-email-worker.service"

# P0: pare o processo antes de qualquer outra mudanca. Esta release NAO
# reinicia o worker; a retomada exige desbloqueio + teste controlado posterior.
if systemctl list-unit-files "$WORKER_UNIT" --no-legend 2>/dev/null | grep -q "$WORKER_UNIT"; then
  "${SUDO[@]}" systemctl stop "$WORKER_UNIT"
fi
if "${SUDO[@]}" systemctl is-active --quiet "$WORKER_UNIT" 2>/dev/null; then
  echo "ERRO: worker continua ativo apos stop" >&2
  exit 10
fi
echo "DEPLOY_WORKER_STOPPED=true"

# Abra a pausa persistente antes de migrations/servicos auxiliares.
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

# Flyway e a fonte de verdade para mudancas de schema/dados.
docker compose run --rm flyway migrate

# Instala monitor, NDR guard, timer diario e migra o link do sentinel para /var/lib.
bash scripts/instalar_monitoramento_vm.sh

# Configura headers de deliverability no Exchange enquanto o worker esta parado.
if ! command -v pwsh >/dev/null 2>&1; then
  echo "ERRO: pwsh nao encontrado na VM" >&2
  exit 11
fi
pwsh -NoProfile -Command '
  $ErrorActionPreference = "Stop"
  if (-not (Get-Module -ListAvailable -Name ExchangeOnlineManagement)) {
    Set-PSRepository -Name PSGallery -InstallationPolicy Trusted
    Install-Module ExchangeOnlineManagement -Scope CurrentUser -Force -AllowClobber
  }
  Import-Module ExchangeOnlineManagement
  Write-Host "EXO_MODULE_READY version=$((Get-Module ExchangeOnlineManagement).Version)"
'
pwsh -NoProfile -File ./scripts/configurar_exchange_deliverability.ps1

# Atestado objetivo do rollout.
SHA="$(git rev-parse HEAD)"
echo "DEPLOY_SHA=$SHA"
test -f "$SENTINEL"
echo "DEPLOY_SENDER_PAUSED=true"
if "${SUDO[@]}" systemctl is-active --quiet "$WORKER_UNIT" 2>/dev/null; then
  echo "ERRO: worker ativo no final da release de hardening" >&2
  exit 12
fi
echo "DEPLOY_WORKER_STOPPED_CONFIRMED=true"
"${SUDO[@]}" systemctl is-active mei-mg-email-monitor.service
"${SUDO[@]}" systemctl is-active mei-mg-email-ndr-guard.service
"${SUDO[@]}" systemctl is-active mei-mg-email-base-sync.timer
"${SUDO[@]}" systemctl is-enabled mei-mg-email-ndr-guard.service
"${SUDO[@]}" systemctl is-enabled mei-mg-email-base-sync.timer

# Confirma V022/V023/V024 no Flyway.
INFO="$(docker compose run --rm flyway info)"
printf '%s\n' "$INFO"
printf '%s\n' "$INFO" | grep -Eq '(^|[[:space:]])22([[:space:]]|\|).*Success|V022' || { echo 'ERRO: V022 nao confirmada' >&2; exit 22; }
printf '%s\n' "$INFO" | grep -Eq '(^|[[:space:]])23([[:space:]]|\|).*Success|V023' || { echo 'ERRO: V023 nao confirmada' >&2; exit 23; }
printf '%s\n' "$INFO" | grep -Eq '(^|[[:space:]])24([[:space:]]|\|).*Success|V024' || { echo 'ERRO: V024 nao confirmada' >&2; exit 24; }

echo "DEPLOY_HARDENING_OK"
echo "WORKER_RESUME_ALLOWED=false"
