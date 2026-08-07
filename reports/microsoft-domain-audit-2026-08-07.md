# Auditoria Microsoft 365 / Cloudflare — 2026-08-07

## Escopo

Dominio de envio: `dev.shopvivaliz.com.br`
Remetente operacional esperado: `naoresponda@dev.shopvivaliz.com.br`
Zona DNS: `shopvivaliz.com.br`

## DNS publico verificado via Cloudflare 1.1.1.1 DoH

Workflow: `Exchange Domain DNS Audit` — run `31185425983` — **SUCCESS**.
Revalidacao manual do mesmo job: attempt 2, concluida em 2026-08-07 14:53 UTC — **SUCCESS**.

Resultado observado na revalidacao:

- Nameservers da zona: `ara.ns.cloudflare.com.` e `roman.ns.cloudflare.com.`
- SPF: `v=spf1 include:spf.protection.outlook.com -all`
- MX: `0 dev-shopvivaliz-com-br.mail.protection.outlook.com.`
- DKIM selector1: `selector1-dev-shopvivaliz-com-br._domainkey.contabilidademelo.a-v1.dkim.mail.microsoft.`
- DKIM selector2: `selector2-dev-shopvivaliz-com-br._domainkey.contabilidademelo.a-v1.dkim.mail.microsoft.`
- DMARC: `v=DMARC1; p=none; rua=mailto:postmaster@dev.shopvivaliz.com.br`
- Autodiscover: `autodiscover.outlook.com.`
- TXT de verificacao Microsoft: presente
- Resultado do script: `READY_DNS_MICROSOFT_CUSTOM_DOMAIN`

Observacao: DMARC esta em `p=none`, apropriado para monitoramento, mas ainda sem politica de quarentena/rejeicao. A politica nao deve ser endurecida para `quarantine`/`reject` sem avaliar antes os relatorios DMARC e todos os remetentes legitimos.

## Prova de envio real Microsoft com dominio customizado

Foi recebido em caixa Gmail um email originado de `naoresponda@dev.shopvivaliz.com.br` e entregue inicialmente pelo Exchange Online. O cabecalho preservado registrou:

- SPF `pass` para `dev.shopvivaliz.com.br`
- DKIM `pass` com `d=dev.shopvivaliz.com.br` e `s=selector1`
- DMARC `pass` para `dev.shopvivaliz.com.br`
- ARC da Microsoft preservando SPF/DKIM/DMARC `pass`

O email foi posteriormente redirecionado pela infraestrutura Titan para a caixa Gmail; a autenticacao da etapa Microsoft foi preservada no ARC.

Uma busca operacional recente na caixa Gmail conectada nao encontrou NDRs Microsoft com codigos de TERRL/throttling como `5.7.233` ou `5.7.236`. Isso e apenas um sinal complementar; a fonte autoritativa para TERRL continua sendo o Exchange Admin Center.

## Estado do repositorio

- `MAX_ENVIOS_POR_DIA=10000`
- `RATE_LIMIT_ENVIOS_POR_MINUTO=20`
- `MICROSOFT_SENDER_DOMAIN=dev.shopvivaliz.com.br`
- `MICROSOFT_GRAPH_USER=naoresponda@dev.shopvivaliz.com.br`
- `BASE_URL_DESCADASTRO=https://dev.shopvivaliz.com.br/descadastro`
- Worker protegido por advisory lock de instancia unica, janela movel de 24 horas, recuperacao de lotes presos e reprogramacao de falhas transitorias conhecidas.
- Microsoft Graph agora preserva o cabecalho `Retry-After` em respostas de throttling e o worker respeita esse backoff antes de uma nova tentativa.
- Erros Graph `TooManyRequests`, `ServiceUnavailable`, HTTP 429/5xx e equivalentes conhecidos sao tratados como transitorios e reprogramados sem multiplicar workers.
- `Email Safety CI` run `31189575517`: **SUCCESS** apos os testes de throttling e `Retry-After`.

## Limites Microsoft que continuam obrigatorios

A autenticacao do dominio nao remove os limites de servico do Exchange Online. O limite de destinatarios e por caixa e usa janela movel de 24 horas; o TERRL e um segundo limite, no nivel do tenant, para destinatarios externos. Atingir um desses limites pode impedir novos envios ate a janela voltar a ficar abaixo do teto.

## Verificacao ainda obrigatoria no Exchange Admin Center

A auditoria nao tem credencial administrativa do tenant para ler diretamente o relatorio TERRL. Antes de declarar a meta de 10.000 destinatarios externos em 24 horas como liberada, confirmar no EAC em **Reports > Mail flow > Tenant Outbound External Recipients**:

- `Threshold` (TERRL) >= 10.000; para operacao com margem, deve haver capacidade adicional para outros envios do tenant.
- `ObservedValue` abaixo do threshold.
- `Verdict` sem bloqueio.
- `EnforcementEnabled` e estado atual conhecidos.
- Tenant nao deve ser trial-only para uma meta de 10.000 externos/dia.

O script `scripts/auditar_exchange_10000.py` exige `MICROSOFT_TERRL_THRESHOLD` confirmado e falha fechado caso a configuracao ou o runtime nao estejam seguros.

## Conclusao

**DNS, Cloudflare e autenticacao do dominio customizado estao prontos e foram revalidados ao vivo.** O fluxo de software tambem foi endurecido para respeitar throttling e backoff da Microsoft. Ainda assim, nao e tecnicamente correto prometer "10.000 por dia sem bloqueios" enquanto o TERRL real do tenant nao for lido no EAC e porque 10.000 e o proprio teto por caixa do Exchange Online. Para bulk comercial continuo no limite, deve-se considerar um servico de envio em massa suportado para esse perfil em vez de depender do Exchange Online como plataforma de bulk mail.
