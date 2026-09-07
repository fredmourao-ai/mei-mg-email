# MEI-MG Email

Sistema de fila, envio e monitoramento de e-mails para a operação MEI/MG da Contabilidade Melo.

## Produção

- Provedor exclusivo: **Brevo Transactional Email API**.
- Plano operacional: **Brevo Free**, com hard cap local de **300 e-mails por janela móvel de 24 horas**.
- Meta operacional: `META_ENVIOS_POR_DIA=295`, mantendo margem abaixo do teto.
- Remetente permitido: `naoresponda@dev.shopvivaliz.com.br`.
- HTTP 201 + `messageId` do Brevo é registrado como `submitted`; não representa entrega confirmada.
- IDs Brevo são persistidos como `brevo:<messageId>` para atribuição inequívoca do provedor.
- Entrega real e hard bounce são reconciliados por `mei-mg-email-brevo-reconciler.service`.
- Worker único por advisory lock do PostgreSQL.
- SMTP, Gmail e caminhos legados Microsoft/Graph não fazem parte do runtime de produção.

## Fila contínua

O `queue_replenisher` mantém o buffer independentemente do worker:

- `QUEUE_MIN_PENDING=14800`
- `QUEUE_TARGET_PENDING=15000`

Enfileirar não consome a cota Brevo. A trava de 300/24h é aplicada imediatamente antes de cada submissão.

## Política de importação

A política canônica está em `AGENTS.md`: empresa deve estar ATIVA; e-mail não pode conter `contabil`; e-mail compartilhado por mais de 2 cadastros não entra; destinatário/CNPJ já enviado ou enfileirado não entra. MG é apenas prioridade de ordenação. Gates legados aposentados não podem voltar ao fluxo operacional.

## Cota e anti-reenvio

A cota móvel conta apenas evidência atribuída ao Brevo:

- `mei_email.envios.provider_message_id LIKE 'brevo:%'` com `submitted_at` nas últimas 24h;
- registros Brevo em `mei_email.envios_externos_cota` para testes/controlados fora da fila.

A proteção contra replay é independente do provedor: uma submissão anterior continua bloqueando reenvio mesmo depois de o status evoluir para `delivered` ou `bounce_permanent`.

## Atualização diária da base

O timer `mei-mg-email-base-sync.timer` executa diariamente às 03:15 em `America/Sao_Paulo`, com `Persistent=true` e atraso aleatório de até 10 minutos.

A rotina `scripts/sincronizar_base_diaria.py` registra cada execução em `mei_email.base_sync_runs` e não cria campanhas nem inicia o worker.

## Reconciliação de entrega Brevo

`mei-mg-email-brevo-reconciler.service` consulta de forma paginada e limitada `/v3/smtp/statistics/events`.

- `delivered` → `delivered`;
- `hardBounce`, `invalid`, `blocked` e `spam` → `bounce_permanent` + suppression técnica;
- eventos transitórios/engagement não tornam o destinatário reenviável.

## Monitoramento residente

`mei-mg-email-monitor.service` observa fila, cota Brevo 24h, advisory lock, falhas, hard bounces, reconciliador Brevo e sincronização diária da base.

O estado operacional persistente fica fora do Git em `/var/lib/mei-mg-email`.

## Instalação dos serviços na VM

```bash
bash scripts/instalar_monitoramento_vm.sh
```

O instalador ativa worker, monitor, timer da base e reconciliador Brevo; também desabilita o NDR Guard legado do Exchange.

## Teste controlado

Com o worker ainda pausado:

```bash
python scripts/enviar_teste_brevo.py
```

O teste envia uma única mensagem interna, registra a submissão na cota e só retorna sucesso após evento Brevo `delivered`.

## Desenvolvimento local

```powershell
docker compose up -d
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements-dev.txt
pytest
```

API local:

```powershell
.\.venv\Scripts\uvicorn app.main:app --reload --port 8000
```

## Segurança

- Nunca commite `.env`, senha, token, API key ou chave privada.
- O CI executa `scripts/auditar_segredos_repo.py` e os gates de governança.
- `BREVO_API_KEY` deve existir apenas no secret store/runtime protegido.
- HTTP 201 não é prova de entrega; somente evento `delivered` fecha a validação de entrega.
