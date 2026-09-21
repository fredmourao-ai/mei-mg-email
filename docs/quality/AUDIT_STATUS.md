# Estado da Auditoria

**Status da Auditoria Extrema V5:** CONCLUÍDA E VALIDADA  
**Status operacional de envio:** **NÃO APTO PARA RETOMAR ENVIOS**

Auditoria Extrema V5 concluída em 2026-09-20 segundo `AUDIT_POLICY.md`, `EXTREME_AUDIT_PROTOCOL.md`, `AUDIT_RUNTIME_PARITY_V1.md`, cobertura universal, auditoria de arquitetura/deploy, self-test de governança e evidência real de produção.

## Escopo e versão coberta
- SHA funcional auditado, mesclado e implantado: `6c64291e97e198c35578372dd15575da7de2fde4` (merge do PR #147).
- PR #144: mergeado; governança global, arquitetura/deploy relocável e proteções do circuit breaker incorporadas ao `main`.
- PR #145: mergeado; política de proveniência de execução incorporada ao `main`.
- PR #147: mergeado pelo gate canônico após os cinco checks exigidos ficarem verdes.
- Checkout produtivo: limpo e fast-forwarded para o SHA funcional acima antes desta atualização documental.
- Provider de envio: Brevo.
- Veredito de envio: **NÃO APTO PARA RETOMAR ENVIOS** enquanto `/var/lib/mei-mg-email/sender_blocked.pause` permanecer presente.

## Stop-the-line de entregabilidade
A coorte que abriu o circuit breaker foi revalidada diretamente no banco:
- 300 submissões Brevo;
- 258 `delivered`;
- 24 `bounce_permanent`;
- 18 ainda registrados como `submitted` com diagnóstico transitório;
- taxa de hard bounce: **8,00%**;
- limite fail-closed: **2,00%**;
- 0 hard bounces sem suppression;
- 0 submissões após a abertura do breaker;
- sentinel aberto em `2026-09-19T12:35:01Z`;
- worker `inactive` de forma deliberada.

A janela móvel atual já não contém aquela coorte e mostra 0 submissões/0 hard bounces nas últimas 24h. Isso **não autoriza remover o sentinel**: a retomada continua dependendo do procedimento explícito de recuperação e validação de nova coorte.

## Evidência real de produção
- `runtime_policy_guard.py`: `RUNTIME_POLICY_GUARD_OK`; contrato de banco/repositório e Flyway 20 alinhados.
- `runtime_sender_preflight.py`: OK; Brevo, remetente, ledger e validação presentes; descadastro público retornando HTTP 200.
- Policy guard do repositório: `REPO_POLICY_GUARD_OK`.
- Self-test da governança: `AUDIT_GOVERNANCE_SELF_TEST=PASS`.
- Testes focais pós-deploy: 21/21 PASS.
- Email Safety CI pós-merge: PASS, incluindo secret scan, PowerShell, dependências, SAST, compile, migrations, policy guard, governance self-test e suíte.
- Repository Governance Gate pós-merge: PASS.
- Repository Policy Guard pós-merge: PASS, incluindo verificação GraphQL de `autoMergeAllowed=false`.
- AI Conflict Resolver pós-merge: self-test PASS; `resolve` corretamente skipped fora de contexto de PR.
- Fila aberta: 14.883 pendentes, 0 `enviando`.
- Violações técnicas/canônicas abertas reportadas pelo monitor: 0.
- E-mails da fila compartilhados por mais de 2 CNPJs: 0 grupos.
- Duplicidades abertas por e-mail: 0 grupos.
- Duplicidades abertas por CNPJ: 0 grupos.
- `stale_enviando_15m`: 0.
- Reconciliador Brevo: ativo, enabled e convergente; polls pós-deploy com `unique=0`.
- Monitor: `health=critical` intencionalmente e somente pelo alerta `sender_block_pause_active`.
- API, monitor, queue replenisher, reconciliador, base-sync timer, autorepair timer e túnel público ativos; worker permanece inativo pelo breaker.
- Units systemd ativos foram renderizados com `/home/ubuntu/mei-mg-email` e o Python da `.venv`, sem paths fixos antigos.
- Root filesystem: **82%**, abaixo do limiar crítico de 90%.

## Filtros canônicos
Os únicos filtros de negócio/segmentação permanecem:
1. empresa diferente de ATIVA;
2. e-mail contendo `contabil`;
3. e-mail compartilhado por mais de 2 cadastros;
4. destinatário/CNPJ já enviado ou já enfileirado.

MG é somente prioridade de ordenação, nunca filtro. E-mail inválido/ausente, opt-out, suppression técnica e divergência entre o e-mail atual da empresa e o e-mail enfileirado continuam como proteções técnicas fail-closed, não filtros comerciais adicionais. Gates legados como `uf='MG'`, `filter_not_mei` e `insert_filter_gate` não foram reintroduzidos.

## Backup, restore e desastre
A recuperação deixou de ser dívida de evidência. O workflow `Backend Serial Restore Proof 2026-09-19` concluiu com sucesso e log persistente:
- `mei-email-latest.dump: OK` no SHA-256;
- `RESTORE_ENTRIES=115`;
- `RESTORE_TABLES=10`;
- `RESTORE_EMPRESAS=27979461`;
- `RESTORE_ENVIOS=172025`;
- `RESTORE_INVALID_INDEXES=0`;
- `RESTORE_AUDIT_OK`;
- `RESTORE_CLEANUP_OK`;
- disco ao final do restore: 88%.

O restore foi executado serialmente em PostgreSQL 16 isolado, evitando o pico de disco da tentativa paralela anterior.

Risco residual: o backup comprovado permanece semanal (`Sun 04:30 UTC`), portanto o RPO potencial ainda é de vários dias. A política de lifecycle/retention do bucket continua sem prova operacional suficiente para aumentar frequência com segurança.

## Governança e arquitetura/deploy
O PR #147 fechou um falso-verde real do gate de auto-merge. A consulta REST com token read-only não expunha de forma confiável `allow_auto_merge`; o gate foi corrigido via GraphQL `repository.autoMergeAllowed`, coberto por teste RED/GREEN e validado no GitHub Actions real.

O instalador canônico agora:
- renderiza API, monitor, replenisher e autorepair de forma relocável;
- habilita o timer de autorepair;
- preserva o worker parado quando o circuit breaker existe;
- falha se detectar worker ativo indevidamente sob breaker.

O deploy pós-merge foi executado pelo instalador canônico e terminou com `WORKER_MANTIDO_PARADO_POR_CIRCUIT_BREAKER` e `DEPLOY_SCRIPT_OK`.

## Matriz de cobertura
| Área | Auditada | Resultado atual | Evidência |
| --- | --- | --- | --- |
| Backend | Sim | corrigido; envio pausado por segurança | runtime + testes + systemd |
| Banco/dados | Sim | fila canônica sem violações/duplicidades/stale | queries reais + monitor |
| APIs | Sim | preflight e descadastro OK | HTTP 200 + runtime preflight |
| Jobs/filas/cron | Sim | serviços/timers esperados ativos; worker fail-closed | systemd |
| Integração Brevo | Sim | reconciliador convergente; breaker preservado | DB + journald |
| Segurança/política | Sim | guards e filtros canônicos preservados | policy guard + CI |
| Testes/CI/CD | Sim | gates PR e pós-merge verdes | GitHub Actions |
| Infraestrutura | Sim | disco 82%, abaixo do crítico | `df` |
| Logs/monitoramento | Sim | crítico intencional apenas pelo sentinel | journald + monitor |
| Backup/restore | Sim | restore real comprovado e cleanup concluído | workflow persistente |
| Frontend/UX | N/A | sem superfície end-user principal neste repo | escopo |
| Webhooks | N/A | Brevo usa polling determinístico | arquitetura |
| Dependências/supply chain | Sim | gates atuais verdes | Email Safety CI |

## Reauditoria contraditória
- Tentativa de provar reintrodução de filtros antigos: não encontrada em caminhos operacionais.
- Tentativa de encontrar e-mail compartilhado por >2 CNPJs na fila aberta: 0 grupos.
- Tentativa de encontrar duplicidade aberta por e-mail/CNPJ: 0/0.
- Tentativa de encontrar `enviando` stale: 0.
- Tentativa de provar replay após o breaker: 0 submissões.
- Tentativa de encontrar hard bounce sem suppression na coorte do breaker: 0.
- Tentativa de provar reaplicação contínua de eventos Brevo: polls convergiram para `unique=0`.
- Tentativa de provar drift de release: checkout produtivo e SHA funcional auditado coincidem antes desta atualização documental.
- Tentativa de quebrar o gate de merge: o PR #147 só foi mesclado depois de branch atualizada e todos os checks exigidos verdes; merge prematuro foi corretamente bloqueado pela proteção.

## Achados abertos / risco residual
### P1 — entregabilidade
**COMPROVADO E CONTIDO.** A coorte histórica foi 24/300 = 8,00%. O stop-the-line funcionou e permanece ativo. Não remover o sentinel nem iniciar o worker sem o procedimento específico de recuperação e nova validação controlada.

### P2 — RPO semanal
O restore está comprovado, mas a frequência de backup ainda implica potencial perda de vários dias em desastre. Alterar frequência requer retenção/lifecycle/custo comprovados.

## Meta-auditoria
1. Classe de falha residual mais provável: deterioração futura da qualidade de contatos/entregabilidade ou crescimento de storage compartilhado.
2. Principal dívida de evidência restante: lifecycle/retention efetivo do Object Storage, não o restore.
3. Se este relatório estiver errado, a área mais provável é RPO/retention futura; fila, anti-replay, breaker, restore e runtime parity têm evidência direta atual.
4. Maior risco operacional imediato: remoção manual do sentinel antes de um recovery validado. O sistema permanece fail-closed contra isso no fluxo normal.

## Condições para retomar envios
1. executar o procedimento explícito de recuperação do circuit breaker;
2. validar novamente a origem/qualidade dos destinatários sem criar filtros comerciais novos;
3. manter preflight e iniciar somente canário controlado;
4. observar nova coorte real sem ultrapassar o limite de 2%;
5. manter suppressions, anti-replay e monitoramento ativos.

## Regra de validade
Esta auditoria cobre o comportamento funcional do SHA `6c64291e97e198c35578372dd15575da7de2fde4` e o runtime observado em produção em 2026-09-20. Esta alteração é apenas documental; após seu merge, o checkout produtivo deve ser fast-forwarded ao `main` final sem reiniciar o worker nem remover o circuit breaker.
