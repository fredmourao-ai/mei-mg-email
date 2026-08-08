# Disparo Contabilidade Melo - MEI

## Estado atual

O projeto usa Microsoft Graph com autenticacao App-Only por certificado X.509 na Oracle VM. SMTP AUTH, Gmail, Brevo, client secret e login Graph interativo/delegado ficam desabilitados no runtime de producao.

O dominio de envio de volume e `dev.shopvivaliz.com.br`, com remetente operacional `naoresponda@dev.shopvivaliz.com.br`. O dominio foi validado publicamente para Microsoft 365 com SPF, MX, DKIM (selector1/selector2), DMARC, autodiscover e TXT de verificacao Microsoft. A auditoria automatizada esta em `scripts/auditar_dns_microsoft.py`.

Importante: DNS autenticado melhora identidade e entregabilidade, mas nao remove os limites do Exchange Online nem garante ausencia de bloqueios antispam. O projeto opera fail-closed dentro dos limites configurados e preserva margem na janela movel de 24 horas.

## Limites operacionais

- `MAX_ENVIOS_POR_DIA=10000`: teto local em janela movel de 24 horas.
- `META_ENVIOS_POR_DIA=9950`: meta operacional, mantendo margem de 50 destinatarios abaixo do teto local.
- `RATE_LIMIT_ENVIOS_POR_MINUTO=30`: taxa operacional configurada para o worker; o codigo continua tratando `Retry-After`, throttling e falhas transitorias.
- Apenas um worker de envio pode ficar ativo; uma advisory lock no Postgres impede multiplicacao acidental da taxa.
- O worker reprograma falhas transitorias, recupera lotes presos e devolve o lote para a fila quando a cota de 24 horas e atingida.
- O TERRL do tenant e um limite separado e deve permanecer suficiente para a meta operacional.
- Nunca usar o dominio padrao `*.onmicrosoft.com` para o disparo de volume externo.

## Configuracao de producao

```ini
EMAIL_PROVIDER=microsoft_graph
MICROSOFT_GRAPH_AUTH_MODE=app_only_cert
MICROSOFT_SENDER_DOMAIN=dev.shopvivaliz.com.br
MICROSOFT_GRAPH_TENANT_ID=ID_DO_TENANT
MICROSOFT_GRAPH_CLIENT_ID=ID_DO_APLICATIVO
MICROSOFT_GRAPH_USER=naoresponda@dev.shopvivaliz.com.br
MICROSOFT_GRAPH_CERT_PATH=/home/ubuntu/.shopvivaliz/m365/graph-auth.crt
MICROSOFT_GRAPH_KEY_PATH=/home/ubuntu/.shopvivaliz/m365/graph-auth.key
MAIL_FROM=Contabilidade Melo <naoresponda@dev.shopvivaliz.com.br>
MAIL_FROM_NAME=Contabilidade Melo
MAX_ENVIOS_POR_DIA=10000
META_ENVIOS_POR_DIA=9950
RATE_LIMIT_ENVIOS_POR_MINUTO=30
BASE_URL_DESCADASTRO=https://dev.shopvivaliz.com.br/descadastro
```

A chave privada e o certificado de autenticacao pertencem ao filesystem protegido da VM e nunca devem ser commitados. O runtime nao aceita `MICROSOFT_GRAPH_CLIENT_SECRET`.

## Checklist antes de liberar volume

1. Rode `python scripts/auditar_dns_microsoft.py` e exija `READY_DNS_MICROSOFT_CUSTOM_DOMAIN`.
2. Rode `python scripts/auditar_graph_token.py` e exija `GRAPH_APP_ONLY_TOKEN_READY`, `role_Mail.Send=true` e o remetente oficial.
3. Rode `python scripts/auditar_exchange_10000.py` no mesmo ambiente do worker e exija readiness sem erros bloqueantes.
4. Confirme `RATE_LIMIT_ENVIOS_POR_MINUTO=30`, `META_ENVIOS_POR_DIA=9950` e `MAX_ENVIOS_POR_DIA=10000`.
5. Confirme que a fila nao possui duplicados nem destinatarios ja `submitted`/`enviado` e que todos os pendentes continuam elegiveis.
6. Inicie somente um worker; a advisory lock do Postgres e a cota movel de 24 horas permanecem obrigatorias.

## Arquivos principais

- `templates/mei-contabilidade-melo.html`: template HTML da campanha.
- `scripts/auditar_graph_token.py`: auditoria do token App-Only e role `Mail.Send`.
- `scripts/auditar_dns_microsoft.py`: auditoria DNS publica.
- `scripts/auditar_exchange_10000.py`: auditoria do runtime, banco e limites.
- `scripts/disparar_10000_mei_mg.py`: controlador de capacidade diaria.
- `worker/worker.py`: envio real, cota movel, retries, deduplicacao e recuperacao.
