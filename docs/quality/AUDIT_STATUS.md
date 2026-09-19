# Estado da Auditoria

**Status:** NÃO APTO

Auditoria extrema concluída em 2026-09-19 segundo `EXTREME_AUDIT_PROTOCOL.md`, `AUDIT_RUNTIME_PARITY_V1.md`, a política canônica do repositório e evidência real de produção.

## Escopo e versão coberta
- SHA funcional auditado e implantado: `a2acd724a9f1700ba5e93dc792033a658463c905`.
- Runtime produtivo: checkout limpo, alinhado ao `main`.
- Provider de envio: Brevo.
- Veredito: **NÃO APTO PARA RETOMAR ENVIOS** enquanto o circuit breaker de entregabilidade permanecer aberto.
- Motivo do NO-GO: coorte real das últimas 24h com **24 hard bounces em 300 submissões = 8,00%**, acima do limite fail-closed de **2,00%**.
- O estado de NO-GO é uma proteção correta: o worker está inativo, o sentinel canônico está presente e houve **0 submissões após a abertura do circuito**.

## Correções executadas nesta auditoria
1. Falso-verde de fila: monitor e autorepair passaram a detectar envios abertos que perderam elegibilidade.
2. Drift cadastral: envios abertos agora são comparados ao e-mail atual da empresa; 43 divergências reais foram bloqueadas.
3. Política canônica completa: recovery/autorepair cobrem opt-out, situação cadastral, e-mail atual/válido, suppressions, compartilhamento, anti-replay e duplicidade aberta.
4. Túnel público: ciclo de vida do reverse tunnel foi ligado à API; restart da API mantém descadastro público operacional.
5. Brevo: payload real `hardbounces` passou a ser reconhecido e reconciliado como `bounce_permanent` com suppression.
6. Dedupe Brevo: ledger de eventos passou a preservar ordem recente e convergiu de reaplicações repetidas para `last_unique=0`.
7. Evidência de reconciliação: primeiro `reconciled_at` é preservado; eventos transitórios recebem diagnóstico sem reabrir possibilidade de replay.
8. Circuit breaker de entregabilidade: envio para automaticamente quando a taxa de hard bounce excede 2% com amostra mínima de 50.
9. Capacidade: root filesystem saiu de 95% crítico para 89% warning após limpeza conservadora de caches e workspaces Git limpos/inativos.

## Evidência real de produção
- `runtime_policy_guard.py`: OK; contrato de banco/repositório e Flyway 20 alinhados.
- `runtime_sender_preflight.py`: OK; Brevo, remetente, ledger, validação e descadastro público HTTP 200.
- Testes focais pós-deploy no SHA funcional: **61 passed**.
- Fila: **0 violações canônicas abertas**, 0 duplicidades abertas por e-mail/CNPJ e 0 `enviando` stale.
- Reconciliador Brevo: ativo e convergente; polls recentes com `last_unique=0`.
- Coorte 24h: 300 submetidos, 258 delivered, 24 `bounce_permanent`, 18 `submitted` com diagnóstico transitório.
- Os 24 hard bounces estão suprimidos; causas observadas são caixas inexistentes/indisponíveis (550/552), não erro de sintaxe da aplicação.
- Sentinel aberto em 2026-09-19T12:35:01Z por entregabilidade; worker inativo; **0 submissões após o bloqueio**.
- Monitor: `health=critical` de forma intencional, com alertas `sender_block_pause_active` e `hard_bounce_rate_excessive`.
- API, reverse tunnel, reconciliador, monitor e replenisher permanecem ativos; NDR legado permanece desabilitado.
- Filtros retirados não estão ativos em produção; referências restantes aparecem apenas em histórico/migrations arquivadas ou guards negativos que impedem reintrodução.

## Backup, restore e desastre
- Backup PostgreSQL verificado por custom dump, catálogo `pg_restore -l`, SHA-256, tamanho remoto e manifest.
- Dump auditado: aproximadamente 1,26 GB, 115 objetos restauráveis.
- Restore integral foi executado em PostgreSQL 16 isolado, sem porta publicada; SHA do dump passou, o restore avançou por carga e construção do índice principal sobre a base completa e o harness encerrou pelo caminho de cleanup de sucesso.
- Dívida de evidência: o stdout terminal com as contagens finais do restore não permaneceu disponível no histórico da ferramenta; a conclusão é sustentada pela semântica do harness e ausência dos artefatos que só são removidos após as validações.
- O timer de backup atual é **semanal** (`Sun 04:30 UTC`). Isso implica RPO potencial de vários dias e permanece risco residual relevante.
- Object Storage possui versão do objeto, porém a identidade operacional não expõe a política de lifecycle do bucket; a frequência não foi aumentada sem prova de retenção/custo.

## Matriz de cobertura
| Área | Auditada | Problemas | Corrigidos | Pendentes / ressalvas | Evidência |
| --- | --- | ---: | ---: | --- | --- |
| Backend | Sim | 5 | 5 | worker parado por segurança | testes, runtime, serviços |
| Banco/dados | Sim | 4 | 4 | nenhuma violação canônica aberta | queries reais, Flyway 20 |
| APIs | Sim | 1 | 1 | nenhuma | health/preflight/descadastro |
| Jobs/filas/cron | Sim | 4 | 4 | envio suspenso por circuit breaker | systemd, timers, monitor |
| Integração Brevo | Sim | 4 | 4 | 18 transitórios aguardam eventual evento terminal, sem replay | API events + DB |
| Segurança/política | Sim | 2 | 2 | nenhuma regressão ativa conhecida | policy guards + CI |
| Testes/CI/CD | Sim | 2 | 2 | nenhuma | PRs #134–#140 verdes |
| Infraestrutura | Sim | 2 | 2 | disco 89% = warning | disk guard + df |
| Logs/monitoramento | Sim | 2 | 2 | health crítico intencional até recuperação | journald + monitor |
| Backup/restore | Sim | 2 | 1 | RPO semanal; stdout terminal do restore não retido | dump/sha/restore harness |
| Frontend/UX | N/A | 0 | 0 | repo não possui superfície end-user principal | escopo do projeto |
| Webhooks | N/A | 0 | 0 | Brevo usa polling determinístico | arquitetura atual |
| Dependências/supply chain | Sim | 0 | 0 | nenhuma falha aberta nos gates atuais | Email Safety CI |

## Achados abertos
### P1 — entregabilidade acima do limite
**COMPROVADO E CONTIDO.** 24/300 = 8,00% hard bounce. Todos os 24 estão em estado terminal/suppression e o circuito impediu novos envios. A causa predominante é mailbox inexistente/indisponível. Não remover o sentinel enquanto a janela/coorte não estiver novamente dentro da política e a recuperação não for validada.

### P2 — RPO semanal
O backup comprovado é semanal. Em desastre, suppressions, anti-replay e histórico recente podem perder vários dias. Aumentar frequência exige definir retenção/lifecycle/custo antes de criar múltiplas versões do dump.

### P2 — capacidade do host
O root caiu de 95% para 89%, saindo de crítico para warning. Continuar acompanhando crescimento do volume PostgreSQL e dos demais projetos que compartilham o host.

### P3 — evidência terminal do restore
O restore integral foi executado pelo harness fail-fast e atingiu cleanup de sucesso, mas o stdout terminal com contagens não ficou retido. Repetir o próximo restore periódico com log persistente assinado elimina essa dívida de evidência.

## Reauditoria contraditória
- Tentativa de encontrar filtros retirados em paths ativos: nenhum gate antigo ativo; ocorrências remanescentes são histórico arquivado ou guards negativos.
- Tentativa de encontrar fila inelegível/duplicada/replay/stale: zero ocorrências abertas.
- Tentativa de provar que o reconciliador Brevo repete eventos: estado convergiu para `last_unique=0`.
- Tentativa de provar envio após stop-the-line: **0 submissões** após abertura do sentinel.
- Tentativa de atribuir hard bounce a falha de sender: motivos 550/552 apontam caixas inexistentes/indisponíveis, não bloqueio do remetente.
- Tentativa de provar drift de release: checkout produtivo limpo e alinhado ao SHA auditado antes deste commit documental.

## Meta-auditoria
1. Classe de falha mais provável fora desta auditoria: deterioração futura de dados de contato/entregabilidade e crescimento de storage compartilhado.
2. Maior suposição residual: retenção/versionamento efetivo do bucket OCI, pois a identidade atual lista versões de objeto mas não pode ler a política do bucket.
3. Se o veredito estiver errado, a área mais provável é recuperação de desastre/RPO, não anti-replay ou fila.
4. Risco capaz de causar efeito externo incorreto hoje: remover manualmente o sentinel antes da recuperação de entregabilidade. O sistema não faz isso automaticamente.

## Condições para sair do NO-GO
1. taxa de hard bounce da coorte corrente voltar para dentro do limite de 2%;
2. investigar/limpar novas fontes de destinatários inválidos sem reintroduzir filtros retirados;
3. executar o procedimento documentado de recuperação do circuit breaker, mantendo preflight e canário controlado;
4. observar nova coorte real sem ultrapassar o limite;
5. definir RPO/retention do backup e reduzir a janela de perda conforme o requisito operacional.

## Regra de validade
Esta auditoria cobre o comportamento funcional do SHA `a2acd724a9f1700ba5e93dc792033a658463c905` e o runtime observado em 2026-09-19. O commit deste arquivo é documental; após merge deve ser fast-forwarded no checkout produtivo para manter a proveniência exata do repositório.
