# MEI-MG Email

Sistema de fila, envio e monitoramento de e-mails para a operação MEI/MG da Contabilidade Melo.

## Produção

- Provedor exclusivo: **Brevo Transactional Email API**.
- Plano operacional: **Brevo Free**, com hard cap local de **300 e-mails por janela móvel de 24 horas**.
- Meta operacional explicitamente aprovada: `META_ENVIOS_POR_DIA=300`; o hard cap continua `MAX_ENVIOS_POR_DIA=300` e nunca pode ser excedido.
- Remetente permitido: `atendimento@shopvivaliz.com.br`.
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

A política canônica está em `AGENTS.md`. Os únicos filtros de negócio/segmentação são: empresa ATIVA, bloqueio de e-mail contendo `contabil`, limite de até 2 cadastros por e-mail compartilhado e anti-reenvio/anti-duplicidade por destinatário/CNPJ. E-mail ausente/inválido, opt-out, suppression técnica e divergência entre cadastro atual e fila são proteções técnicas fail-closed, não novos filtros de segmentação. MG é apenas prioridade de ordenação. Gates legados aposentados não podem voltar ao fluxo operacional.

A importação da Receita mantém escopo nacional. A regra de e-mail compartilhado é aplicada pelo `queue_manager` contra a tabela completa `mei_email.empresas`, garantindo a contagem global antes do enfileiramento sem exigir staging temporário de toda a base mensal.

## Cota e anti-reenvio

A cota móvel conta apenas evidência atribuída ao Brevo:

- `mei_email.envios.provider_message_id LIKE 'brevo:%'` com `submitted_at` nas últimas 24h;
- registros Brevo em `mei_email.envios_externos_cota` para testes/controlados fora da fila.

A proteção contra replay é independente do provedor: uma submissão anterior continua bloqueando reenvio mesmo depois de o status evoluir para `delivered` ou `bounce_permanent`.

## Atualização da base oficial

O timer `mei-mg-email-base-sync.timer` executa diariamente às 03:15 em `America/Sao_Paulo`, com `Persistent=true` e atraso aleatório de até 10 minutos.

A fonte padrão é `CNPJ_DAILY_SOURCE=receita_webdav`, usando o compartilhamento público oficial da Receita Federal em `arquivos.receitafederal.gov.br`. A rotina faz um `PROPFIND` leve para localizar a competência `YYYY-MM` mais recente. Se a competência já foi importada com sucesso, registra `no_change` e não baixa ZIPs.

Quando surge uma competência nova, os dez arquivos `Estabelecimentos0.zip` a `Estabelecimentos9.zip` são validados e processados sequencialmente: um ZIP por vez, leitura direta de dentro do arquivo compactado, sem extração do CSV gigante, com reserva mínima de disco e remoção imediata do ZIP após processamento. Uma competência parcial ou ZIP truncado/corrompido nunca é registrado como sucesso.

Casa dos Dados e o espelho Hugging Face permanecem apenas como modos explícitos de fallback/manual; não são requisitos da atualização normal de produção.

A rotina `scripts/sincronizar_base_diaria.py` registra cada execução em `mei_email.base_sync_runs` e não cria campanhas nem inicia o worker de e-mail.

## Reconciliação de entrega Brevo

`mei-mg-email-brevo-reconciler.service` consulta de forma paginada e limitada `/v3/smtp/statistics/events`.

- `delivered` → `delivered`;
- `hardBounce`/`hardbounces`, `invalid`, `blocked` e `spam` → `bounce_permanent` + suppression técnica;
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
