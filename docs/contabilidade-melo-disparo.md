# Disparo Contabilidade Melo - MEI

## Estado operacional atual

A producao usa Microsoft Graph App-Only com certificado X.509 armazenado somente na Oracle VM. SMTP AUTH, Gmail SMTP, Brevo, client secret e autenticacao Graph interativa/delegada estao desabilitados no runtime.

Remetente: `naoresponda@dev.shopvivaliz.com.br`.
Dominio: `dev.shopvivaliz.com.br`.

HTTP 202 do Graph significa apenas `submitted`: nunca deve ser tratado como entrega confirmada. NDRs assincronos precisam ser observados pelo `mei-mg-email-ndr-guard.service`.

## Incidente AS(42004) e fail-closed

Quando aparecer `550 5.1.8 ... AS(42004)` ou `550 5.1.90 ... AS:46601`:

1. parar o worker;
2. manter `/var/lib/mei-mg-email/sender_blocked.pause` presente;
3. manter o NDR guard e o monitor ativos;
4. corrigir Restricted entities com `scripts/desbloquear_exchange_app_cert.ps1 -ConfirmUnblock`, usando o certificado administrativo da VM;
5. confirmar que `Get-BlockedSenderAddress` nao retorna mais o remetente;
6. nao remover a pausa nem iniciar volume nessa mesma etapa;
7. fazer teste controlado separado e somente retomar se nao surgir novo NDR de bloqueio.

O deploy de hardening esta em `scripts/deploy_hardening_20260813.sh` e termina obrigatoriamente com `WORKER_RESUME_ALLOWED=false`.

## Limites

- `MAX_ENVIOS_POR_DIA=10000`: teto tecnico local em janela movel de 24h.
- `META_ENVIOS_POR_DIA=9000`: meta operacional com reserva de 1.000 destinatarios abaixo do limite Exchange de 10.000/24h.
- `RATE_LIMIT_ENVIOS_POR_MINUTO=30`: valor configuravel legado/teto local.
- `DELIVERABILITY_MAX_ENVIOS_POR_MINUTO=10`: cap de recuperacao de reputacao.
- Taxa efetiva: menor valor entre os dois limites acima e 30/min; com os defaults atuais, **10/min**.
- Somente um worker pode possuir a advisory lock global de envio.

## Politica de elegibilidade

A fonte de verdade e `AGENTS.md`. O fluxo de primeiro contato considera apenas a politica canonica atual; gates legados aposentados nao podem ser reintroduzidos por importacao, migration, trigger, guard ou supervisor. `opt_out` e suppressions tecnicas continuam soberanos, e o historico de envio deve ser preservado.

## Deliverability

O envio MIME inclui `List-Unsubscribe` e `List-Unsubscribe-Post`. O Exchange tambem deve ter as regras criadas por `scripts/configurar_exchange_deliverability.ps1`, que asseguram:

- `List-Unsubscribe-Post: List-Unsubscribe=One-Click`;
- `Feedback-ID: meimg:marketing:contamelo:VivalizMEI`.

O assunto/template de campanhas ainda pendentes e normalizado pela V024 para a copia atual de recuperacao de reputacao.

## Configuracao principal

```ini
EMAIL_PROVIDER=microsoft_graph
MICROSOFT_GRAPH_AUTH_MODE=app_only_cert
MICROSOFT_GRAPH_USER=naoresponda@dev.shopvivaliz.com.br
MICROSOFT_GRAPH_CERT_PATH=/home/ubuntu/.shopvivaliz/m365/graph-auth.crt
MICROSOFT_GRAPH_KEY_PATH=/home/ubuntu/.shopvivaliz/m365/graph-auth.key
MAIL_FROM=Contabilidade Melo <naoresponda@dev.shopvivaliz.com.br>
MAX_ENVIOS_POR_DIA=10000
META_ENVIOS_POR_DIA=9000
EXCHANGE_RECIPIENT_SAFETY_RESERVE=1000
RATE_LIMIT_ENVIOS_POR_MINUTO=30
DELIVERABILITY_MAX_ENVIOS_POR_MINUTO=10
SENDER_BLOCK_SENTINEL_PATH=/var/lib/mei-mg-email/sender_blocked.pause
NDR_GUARD_POLL_SECONDS=60
MONITOR_NDR_GUARD_UNIT=mei-mg-email-ndr-guard.service
```

A chave privada, tokens, senhas e arquivos de segredo nunca devem ser versionados.

## Checklist de liberacao

1. `scripts/auditar_graph_token.py`: validar app-only e `Mail.Send`.
2. `scripts/auditar_graph_mail_read.py`: validar `Mail.Read` para o NDR guard.
3. `scripts/auditar_dns_microsoft.py`: validar DNS do dominio.
4. `scripts/auditar_exchange_10000.py`: validar banco, fila, limites e runtime.
5. confirmar monitor + NDR guard + timer diario ativos.
6. confirmar ausencia de Restricted entity/AS(42004).
7. fazer apenas um teste controlado.
8. somente depois remover a pausa persistente e iniciar o worker.

## Arquivos principais

- `worker/worker.py`
- `scripts/ndr_guard.py`
- `scripts/monitor_operacao.py`
- `scripts/deploy_hardening_20260813.sh`
- `scripts/desbloquear_exchange_app_cert.ps1`
- `scripts/configurar_exchange_deliverability.ps1`
- `scripts/sincronizar_base_diaria.py`
- `scripts/ingest_casa_dos_dados_daily.py`
- `templates/mei-contabilidade-melo.html`
