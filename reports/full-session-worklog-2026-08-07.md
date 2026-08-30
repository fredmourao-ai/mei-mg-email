# Worklog completo — e-mail / Microsoft / Cloudflare — 2026-08-07

Este documento resume todas as alteracoes e validacoes feitas nesta sessao no repositorio `fredmourao-ai/mei-mg-email`.

## Objetivo operacional

- Meta solicitada: 9.950 destinatarios por janela movel de 24 horas.
- Teto tecnico local mantido em 10.000/24h.
- Rate local mantido em 20 mensagens/minuto.
- Provedor principal: Microsoft Graph.
- Remetente esperado: `naoresponda@dev.shopvivaliz.com.br`.
- Dominio de envio: `dev.shopvivaliz.com.br`.

## DNS / Cloudflare / Microsoft 365

Foi validado o dominio customizado usado no envio. A auditoria DNS confirma:

- zona `shopvivaliz.com.br` delegada a nameservers Cloudflare;
- SPF Microsoft 365;
- MX para Exchange Online;
- DKIM selector1 e selector2;
- DMARC presente;
- autodiscover Microsoft;
- TXT de verificacao Microsoft.

Script de auditoria: `scripts/auditar_dns_microsoft.py`.
Workflow: `.github/workflows/exchange-domain-dns-audit.yml`.

Tambem foi registrada evidencia de mensagem real autenticada com SPF/DKIM/DMARC pass em `reports/microsoft-domain-audit-2026-08-07.md`.

Observacao importante: DNS correto nao substitui a confirmacao do TERRL no Exchange Admin Center nem garante ausencia de throttling/antispam dinamico.

## Microsoft Graph

Foram reforcados os seguintes pontos:

- tratamento de throttling e erros transitorios;
- respeito a `Retry-After` quando a Microsoft devolver 429/503;
- rotina de preflight nao interativa para validar o cache/token no proprio host do worker;
- nenhuma exibicao de token em logs.

Arquivo novo: `scripts/auditar_graph_token.py`.

O script valida se o token/cache pode ser reutilizado/renovado silenciosamente e se o principal corresponde ao remetente configurado.

## Auditoria Exchange / 9.950

`scripts/auditar_exchange_10000.py` foi convertido em auditoria fail-closed para a meta operacional de 9.950.

Ele agora exige e valida:

- provider Microsoft/Graph;
- `MAX_ENVIOS_POR_DIA=10000`;
- `META_ENVIOS_POR_DIA=9950`;
- rate <= 30/min;
- remetente no dominio `dev.shopvivaliz.com.br`;
- `MAIL_FROM` coerente;
- descadastro HTTPS;
- template HTML oficial;
- `MICROSOFT_TERRL_THRESHOLD` >= meta operacional;
- DNS pronto;
- token Graph pronto no host;
- banco acessivel;
- fila dentro da meta;
- sem lotes travados;
- sem destinatarios nao elegiveis na fila;
- sem repeticao de e-mail no historico de envios;
- taxa de falha aceitavel.

Status de liberacao esperado:

`READY_FOR_AUTHORIZED_RECIPIENTS_WITHIN_CONFIGURED_LIMITS`

## Meta 9.950 separada do teto 10.000

`app/config.py` passou a ter duas variaveis distintas:

- `MAX_ENVIOS_POR_DIA=10000` — teto tecnico;
- `META_ENVIOS_POR_DIA=9950` — meta operacional.

O worker usa a menor das duas como limite efetivo de envio em 24h. Assim, ele para em 9.950 mesmo que a trava tecnica esteja em 10.000.

## Controle de destinatarios

Foi criada a migration:

`db/migrations/V010__eligibility_consent_and_global_dedupe.sql`

Ela adiciona:

- `campo_autorizacao_legado`;
- `campo_autorizacao_legado_em`;
- `campo_autorizacao_legado_origem`;
- status de envio `bloqueado`;
- indice por e-mail normalizado;
- nova `vw_empresas_elegiveis` fail-closed.

A view so libera:

- empresa `ATIVA`;
- sem opt-out;
- nao marcada como terceiro;
- com e-mail valido;
- ainda nao marcada como enviada;
- `campo_autorizacao_legado=true`;
- sem qualquer registro previo do mesmo e-mail normalizado em `envios`.

Assim, o mesmo e-mail nao volta para a fila, mesmo se aparecer em outro CNPJ.

## Rechecagem no momento do envio

`worker/worker.py` passou a revalidar antes de cada mensagem:

- opt-out;
- situacao cadastral ATIVA;
- `campo_autorizacao_legado=true`.

Se alguma dessas condicoes falhar depois do enfileiramento, o envio vira `bloqueado` ou `opt_out` e nao e enviado.

O worker tambem:

- mantem advisory lock para somente uma instancia;
- respeita a janela movel de 24h;
- para em 9.950;
- recupera lotes presos;
- reprograma falhas transitorias;
- respeita Retry-After;
- atualiza historico por e-mail normalizado.

## Template HTML oficial

O disparador diario agora usa obrigatoriamente:

`templates/mei-contabilidade-melo.html`

Ele valida a presenca de:

- HTML completo;
- `{{nome_fantasia}}`;
- `{{unsubscribe_url}}`;
- `logo-contabilidade-melo-transparente.png` no rodape.

O antigo fluxo de texto simples foi removido da rotina diaria.

Arquivo ajustado:

`scripts/disparar_10000_mei_mg.py`

A meta codificada e 9.950, mantendo o alias antigo para compatibilidade com automacoes existentes.

## Teste Microsoft com o template real

`scripts/enviar_teste_microsoft_graph.py` foi alterado para usar exatamente o template HTML oficial, com descadastro e logo, em vez de um HTML simplificado de teste.

## Importacao diaria / novos cadastros

`scripts/ingest_from_huggingface.py` foi ajustado para sincronizacao diaria incremental e segura.

Comportamento atual:

- novos CNPJs sao inseridos;
- registros existentes recebem refresh apenas de situacao cadastral e classificacao de regime;
- opt-out nunca e apagado;
- historico de envio nunca e zerado;
- consentimento/autorizacao nunca e concedido automaticamente;
- e-mail/contato existente nao e sobrescrito pela carga publica;
- carga parcial aborta a rotina;
- heuristica de terceiros so reforca bloqueio, nunca o remove automaticamente.

Bases publicas entram com `campo_autorizacao_legado=false` por padrao.

## Rotina diaria fail-closed

Foi criado:

`scripts/rotina_diaria_segura.py`

Ordem de execucao:

1. sincronizar base;
2. auditar Exchange/Graph/DNS/TERRL/banco/template;
3. somente se tudo passar, enfileirar a capacidade restante ate 9.950.

O worker de producao continua sendo o unico componente que envia de fato.

## CI e testes

`.github/workflows/email-safety-ci.yml` foi ampliado para acompanhar:

- app;
- worker;
- scripts;
- templates;
- migrations;
- testes de seguranca.

`tests/test_worker_safety.py` passou a cobrir:

- erros Microsoft transitorios;
- Retry-After;
- erros permanentes;
- descadastro;
- meta 9.950 abaixo do teto 10.000;
- template HTML com logo;
- migration de autorizacao/dedupe.

Os workflows de seguranca executados apos as mudancas finalizaram com sucesso.

## Bloqueios remanescentes antes de disparo real

O disparo real foi mantido bloqueado de proposito ate confirmar no ambiente de producao:

1. `scripts/auditar_graph_token.py` retornando `GRAPH_TOKEN_READY` no mesmo host/usuario do worker;
2. TERRL real do tenant no Exchange Admin Center e `MICROSOFT_TERRL_THRESHOLD` configurado com o valor confirmado;
3. banco de producao com migrations aplicadas;
4. destinatarios com `campo_autorizacao_legado=true`;
5. `scripts/auditar_exchange_10000.py` retornando `READY_FOR_AUTHORIZED_RECIPIENTS_WITHIN_CONFIGURED_LIMITS`.

## Seguranca / limites

Nao foi implementado nenhum mecanismo para contornar limites da Microsoft, rotacionar caixas para escapar de TERRL ou ignorar antispam.

A arquitetura ficou preparada para operar dentro dos limites configurados e somente com destinatarios elegiveis/autorizados.
