# Auditoria Microsoft 365 / Cloudflare — 2026-08-07

## Escopo

Dominio de envio: `dev.shopvivaliz.com.br`
Remetente operacional esperado: `naoresponda@dev.shopvivaliz.com.br`
Zona DNS: `shopvivaliz.com.br`

## DNS publico verificado via Cloudflare 1.1.1.1 DoH

Workflow: `Exchange Domain DNS Audit` — run `31185425983` — **SUCCESS**.

Resultado observado:

- Nameservers da zona: `ara.ns.cloudflare.com.` e `roman.ns.cloudflare.com.`
- SPF: `v=spf1 include:spf.protection.outlook.com -all`
- MX: `0 dev-shopvivaliz-com-br.mail.protection.outlook.com.`
- DKIM selector1: `selector1-dev-shopvivaliz-com-br._domainkey.contabilidademelo.a-v1.dkim.mail.microsoft.`
- DKIM selector2: `selector2-dev-shopvivaliz-com-br._domainkey.contabilidademelo.a-v1.dkim.mail.microsoft.`
- DMARC: `v=DMARC1; p=none; rua=mailto:postmaster@dev.shopvivaliz.com.br`
- Autodiscover: `autodiscover.outlook.com.`
- TXT de verificacao Microsoft: presente
- Resultado do script: `READY_DNS_MICROSOFT_CUSTOM_DOMAIN`

Observacao: DMARC esta em `p=none`, apropriado para monitoramento, mas ainda sem politica de quarentena/rejeicao.

## Prova de envio real Microsoft com dominio customizado

Foi recebido em caixa Gmail um email originado de `naoresponda@dev.shopvivaliz.com.br` e entregue inicialmente pelo Exchange Online. O cabeçalho preservado registrou:

- SPF `pass` para `dev.shopvivaliz.com.br`
- DKIM `pass` com `d=dev.shopvivaliz.com.br` e `s=selector1`
- DMARC `pass` para `dev.shopvivaliz.com.br`
- ARC da Microsoft preservando SPF/DKIM/DMARC `pass`

O email foi posteriormente redirecionado pela infraestrutura Titan para a caixa Gmail; a autenticacao da etapa Microsoft foi preservada no ARC.

## Estado do repositorio

- `MAX_ENVIOS_POR_DIA=10000`
- `RATE_LIMIT_ENVIOS_POR_MINUTO=20`
- `MICROSOFT_SENDER_DOMAIN=dev.shopvivaliz.com.br`
- `MICROSOFT_GRAPH_USER=naoresponda@dev.shopvivaliz.com.br`
- `BASE_URL_DESCADASTRO=https://dev.shopvivaliz.com.br/descadastro`
- Worker protegido por advisory lock de instancia unica, janela movel de 24 horas, recuperacao de lotes presos e reprogramacao de falhas transitorias conhecidas.
- `Email Safety CI` run `31185425940`: **SUCCESS**.

## Verificacao ainda obrigatoria no Exchange Admin Center

A auditoria nao tem credencial administrativa do tenant para ler diretamente o relatorio TERRL. Antes de liberar meta de 10.000 destinatarios externos em 24 horas, confirmar no EAC em **Reports > Mail flow > Tenant Outbound External Recipients**:

- `Threshold` (TERRL) >= 10.000; idealmente acima de 10.000 para margem de outros envios do tenant.
- `ObservedValue` abaixo do threshold.
- `Verdict` sem bloqueio.
- `EnforcementEnabled` e estado atual conhecidos.
- Tenant nao deve ser trial-only para uma meta de 10.000 externos/dia.

O script `scripts/auditar_exchange_10000.py` exige `MICROSOFT_TERRL_THRESHOLD` confirmado e falha fechado caso a configuracao ou o runtime nao estejam seguros.

## Conclusao

**DNS e autenticacao do dominio customizado estao prontos e validados publicamente.** A liberacao de 10.000 destinatarios externos/dia no Exchange Online nao deve ser declarada como garantida ate o TERRL real do tenant e o estado do banco/worker de producao serem auditados no ambiente autorizado. Nenhuma configuracao deve tentar contornar os limites ou mecanismos antispam do Microsoft 365.
