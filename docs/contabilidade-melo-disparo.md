# Disparo Contabilidade Melo - MEI

## Estado atual

O projeto usa Microsoft Graph com OAuth2 delegado. O SMTP AUTH do tenant pode permanecer desabilitado; ele nao e necessario para o fluxo Graph.

O dominio de envio de volume e `dev.shopvivaliz.com.br`, com remetente operacional `naoresponda@dev.shopvivaliz.com.br`. O dominio foi validado publicamente para Microsoft 365 com SPF, MX, DKIM (selector1/selector2), DMARC, autodiscover e TXT de verificacao Microsoft. A auditoria automatizada esta em `scripts/auditar_dns_microsoft.py` e roda no workflow `Exchange Domain DNS Audit`.

Importante: DNS autenticado melhora identidade e entregabilidade, mas nao remove os limites do Exchange Online nem garante ausencia de bloqueios antispam. O projeto opera fail-closed dentro dos limites publicados e preserva margem de envio.

## Limites operacionais

- `MAX_ENVIOS_POR_DIA=10000`: teto por caixa em janela movel de 24 horas.
- `RATE_LIMIT_ENVIOS_POR_MINUTO=20`: abaixo do limite de 30 mensagens/minuto para deixar margem contra throttling e outras atividades da caixa.
- Apenas um worker de envio pode ficar ativo; uma advisory lock no Postgres impede multiplicacao acidental da taxa.
- O worker reprograma falhas transitorias, recupera lotes presos e devolve o lote para a fila quando a cota de 24 horas e atingida.
- O TERRL do tenant e um limite separado. Antes de liberar a meta de 10.000 destinatarios externos/dia, confirme no Exchange Admin Center que `Tenant Outbound External Recipients` e pelo menos 10.000 e configure `MICROSOFT_TERRL_THRESHOLD` com esse valor.
- Nunca usar o dominio padrao `*.onmicrosoft.com` para o disparo de volume externo.

## Configuracao de producao

```ini
EMAIL_PROVIDER=microsoft_graph
MICROSOFT_SENDER_DOMAIN=dev.shopvivaliz.com.br
MICROSOFT_GRAPH_TENANT_ID=ID_DO_TENANT
MICROSOFT_GRAPH_CLIENT_ID=ID_DO_APLICATIVO
MICROSOFT_GRAPH_USER=naoresponda@dev.shopvivaliz.com.br
MICROSOFT_GRAPH_TOKEN_CACHE=
MAIL_FROM=Contabilidade Melo <naoresponda@dev.shopvivaliz.com.br>
MAX_ENVIOS_POR_DIA=10000
RATE_LIMIT_ENVIOS_POR_MINUTO=20
BASE_URL_DESCADASTRO=https://dev.shopvivaliz.com.br/descadastro
MICROSOFT_TERRL_THRESHOLD=10000
```

O cache de token deve ficar fora do repositorio. Nunca commitar tokens, senhas ou arquivos de cache OAuth.

## Checklist antes de liberar volume

1. Rode `python scripts/auditar_dns_microsoft.py` e exija `READY_DNS_MICROSOFT_CUSTOM_DOMAIN`.
2. No Exchange Admin Center, confirme que `dev.shopvivaliz.com.br` e Accepted Domain e que DKIM esta habilitado para o dominio.
3. Confirme o TERRL em **Reports > Mail flow > Tenant Outbound External Recipients** e mantenha `MICROSOFT_TERRL_THRESHOLD` igual ao valor observado; precisa ser >= 10000 para a meta solicitada.
4. Rode `python scripts/auditar_exchange_10000.py` no mesmo ambiente do worker e exija `READY_WITHIN_EXCHANGE_SERVICE_LIMITS`.
5. Confirme que a mensagem de teste real chega com SPF, DKIM e DMARC `pass`, usando o remetente `naoresponda@dev.shopvivaliz.com.br`.
6. Inicie somente um worker. Nao aumente o rate para alem de 30/min e nao configure teto acima de 10.000/24h.

## Arquivos principais

- `templates/mei-contabilidade-melo.html`: template HTML da campanha.
- `scripts/autorizar_microsoft_graph.py`: login OAuth por codigo de dispositivo.
- `scripts/enviar_teste_microsoft_graph.py`: teste de envio.
- `scripts/auditar_dns_microsoft.py`: auditoria DNS publica via Cloudflare DoH.
- `scripts/auditar_exchange_10000.py`: auditoria do runtime/banco/limites.
- `scripts/disparar_10000_mei_mg.py`: controlador de capacidade diaria.
- `worker/worker.py`: envio real, cota movel, retries e recuperacao.
