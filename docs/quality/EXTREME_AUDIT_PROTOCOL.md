# Protocolo Universal de Auditoria Extrema — Zero Blind Spots

## Missão
Atue sob três lentes obrigatórias: **Auditor** (conformidade, segurança, integridade e regras), **Consultor** (risco, negócio, UX, custo e produtividade) e **Operador** (reprodução, correção, testes e validação real). As lentes não devem repetir texto: cada uma responde por uma dimensão distinta do mesmo achado.

O objetivo não é gerar um relatório; é executar, conforme acessos e segurança permitirem: **MAPEAR → QUESTIONAR → REPRODUZIR → PROVAR → CORRIGIR → TESTAR → REGREDIR → REAUDITAR**.

## 0. Regras epistemológicas
- Não presuma que documentação, nome de função, teste verde, HTTP 200, botão visível, migration existente, worker configurado ou serviço `active` provam comportamento correto.
- Todo achado é `COMPROVADO`, `FORTE EVIDÊNCIA`, `HIPÓTESE A VALIDAR` ou `NÃO VALIDADO`.
- Tente refutar achados relevantes antes de registrá-los: procure proteção equivalente em outro módulo, constraint, configuração, middleware, worker, feature flag ou fluxo compensatório.
- Para toda área considerada correta, tente construir pelo menos um cenário capaz de quebrá-la.
- Esta lista é requisito mínimo e nunca limita novas classes de risco encontradas durante a auditoria.

## 1. Reconstrução do sistema real
Compare, quando disponíveis: **documentação × código × testes × schema/migrations × dados × configuração × CI/CD × infraestrutura × processos ativos × produção × histórico Git**.

Mapeie entidades, estados, transições, APIs, telas, comandos, jobs, filas, schedulers, cron, webhooks, integrações, storage, caches, feature flags, scripts operacionais, backups, observabilidade e efeitos externos.

Não presuma que o repositório contém toda a realidade: procure configuração manual, serviço legado, script fora do fluxo principal, hotfix, job duplicado e drift entre ambiente declarado e executado.

## 2. Fluxos ponta a ponta e data lineage
Para cada entidade/fluxo crítico trace:
`entrada → validação → persistência → processamento → decisão → efeito externo → confirmação → reconciliação → encerramento`.

Para cada etapa determine: produtor, consumidor, condição, persistência, idempotência, timeout, retry, backoff, deduplicação, compensação, observabilidade, responsável, estado de falha e mecanismo de recuperação.

Rastreie também dados críticos: `origem → transformação → armazenamento → consumidor → decisão → efeito`.

## 3. Espaço negativo: o que deveria existir e não existe
Procure sistematicamente:
- produtor sem consumidor e consumidor sem produtor;
- estado sem transição, timeout, saída ou owner;
- fila sem worker; evento sem listener; botão sem backend; endpoint sem caller; job não agendado;
- dado coletado mas nunca usado/reconciliado;
- falha registrada mas nunca tratada;
- ausência de watchdog, retry, dead-letter, reconciliação, rollback, compensação, cleanup, alerta ou recuperação;
- processo iniciado que pode nunca terminar.

Para cada fluxo pergunte: quem detecta quando **algo esperado não acontece** e quem corrige?

## 4. Invariantes
Derive propriedades que jamais podem ser violadas. Exemplos: não duplicar efeito financeiro; não perder registros silenciosamente; tenant A não acessar tenant B; estado terminal não mudar sem evento explícito; efeito externo não ser considerado concluído sem confirmação; dado derivado reconciliar com fonte.

Crie matriz: `Invariante | Garantia técnica | Teste | Como quebrar | Evidência` e tente deliberadamente violar cada uma.

## 5. Ciclo de vida e máquina de estados
Audite Create/Read/Update/Delete/Archive/Restore/Cancel/Reopen/Retry/Undo conforme aplicável. Mapeie `estado atual → evento → condição → próximo estado` e detecte estados inalcançáveis, eternos, sem saída, transições proibidas, saltos indevidos, reversões ausentes e registros fantasmas presos em CREATED/PENDING/PROCESSING/SUBMITTED/FAILED ou equivalentes.

## 6. Pilares técnicos mínimos
Audite obrigatoriamente quando aplicável:
1. lógica funcional, matemática, moeda, arredondamento, datas, timezone e limites;
2. concorrência, race conditions, locks, idempotência e reexecução;
3. autenticação, autorização, RBAC/ABAC, IDOR, tenant isolation e OWASP;
4. privacidade, LGPD, minimização, retenção, anonimização e deleção;
5. persistência, constraints, FKs, índices, transações, órfãos e migrations;
6. integração entre módulos e propagação de alterações;
7. resiliência a timeout, 429, 5xx, payload inválido, indisponibilidade, restart e processamento parcial;
8. UX, prevenção de erro humano, acessibilidade e continuidade operacional;
9. performance, N+1, pools, memória, disco, storage, crescimento ilimitado e saturação;
10. observabilidade: logs, métricas, tracing, correlation IDs, alertas e healthchecks;
11. CI/CD, artefatos, rollback, config drift, secrets, feature flags e ambientes;
12. supply chain: dependências, lockfiles, imagens, actions de terceiros, licenças, vulnerabilidades e componentes abandonados.

## 7. Tempo, ordem e compatibilidade
Teste T-1/T/T+1 para prazos; UTC versus timezone de negócio; virada de dia/mês/ano; leap year quando pertinente; eventos duplicados, atrasados ou fora de ordem; schema/API/eventos em versões diferentes; backend novo com worker/frontend antigo e vice-versa.

## 8. Dados reais e leakage operacional
Quando autorizado, procure nos dados existentes: duplicidades, órfãos, estados impossíveis, registros antigos demais, nulls inesperados, totais divergentes, timestamps incoerentes, filas acumuladas e entidades que entram no funil mas desaparecem antes do estado final.

Código correto não prova banco íntegro.

## 9. Integrações e efeitos externos
Para cada integração valide:
`input → transformação → request → aceite do provedor → persistência → confirmação do efeito → reconciliação`.

Não confunda `request enviada`, `HTTP 200`, `aceita`, `processada` e `efeito efetivamente realizado`.
Verifique autenticação/expiração, paginação, rate limit, timeout, retry, idempotência, webhook perdido/duplicado, mudança de schema e reconciliação independente.

## 10. Testar os próprios testes
Pergunte: **se o código estivesse errado, esta suíte perceberia?**
Além de unit/integration/E2E, use quando tecnicamente apropriado: property-based testing, contract testing, mutation testing, fuzzing e fault injection. Procure testes que passam sem asserts úteis, mocks excessivos, testes ignorados/flaky e failure paths não cobertos.

## 11. Capacidade, deterioração e time bombs
Determine o primeiro recurso a saturar: CPU, RAM, disco, pool, fila, quota, rate limit, storage ou dependência externa. Procure deterioração silenciosa mesmo com health verde. Audite expiração futura de certificados, tokens, domínios, credenciais, secrets, licenças e limites de fornecedor.

## 12. Backup, restore e desastre
Backup só é comprovado quando a cadeia `backup → integridade → retenção → restore → validação` é demonstrável. Registre RPO/RTO quando aplicável. Backup nunca restaurado deve ser marcado como `RECUPERAÇÃO NÃO COMPROVADA`.

## 13. Proveniência da produção
Quando houver produção, prove a cadeia `commit → build → artefato → release → deploy → processo ativo`. Registre SHA/versão/build/digest/release quando acessível. Se não houver prova de que o software auditado é o executado, marque `VERSÃO EM PRODUÇÃO NÃO COMPROVADA`.

## 14. Segurança adversarial e abuso
Além de vulnerabilidades clássicas, avalie abuso de funcionalidade legítima, escalada horizontal/vertical, manipulação de IDs/tenant/owner, mass assignment, fraude interna/externa e ameaça por usuário autenticado. Construa matriz de autorização por papel/recurso/ação.

## 15. Risco financeiro, operacional e custo
Priorize falhas capazes de gerar perda de receita, cobrança/reembolso duplicado, prazo perdido, ação externa indevida, dado não reconciliado, indisponibilidade, retrabalho ou decisão baseada em dado obsoleto. Avalie também desperdício comprovado: polling, API calls, storage/logs e recursos ociosos.

## 16. Classificação do achado
Para cada achado registre:
- ID e título;
- severidade `P0/P1/P2/P3/P4`;
- probabilidade `Alta/Média/Baixa`;
- blast radius `Global/Módulo/Tenant/Usuário/Registro`;
- detectabilidade `Fácil/Moderada/Difícil/Silenciosa`;
- confiança/evidência;
- arquivo/linha ou componente;
- visão Auditor: falha, evidência, regra violada;
- visão Consultor: impacto real e recomendação;
- visão Operador: reprodução, causa raiz, correção, teste antes/depois e risco de regressão.

Severidade: P0 = perda/corrupção/segurança crítica/indisponibilidade grave atual; P1 = alto impacto provável; P2 = falha relevante contornável; P3 = impacto limitado/dívida/UX/observabilidade; P4 = melhoria sem defeito atual.

## 17. Segurança da correção
Antes de alterar classifique a ação:
- `SAFE`: local e comprovadamente segura;
- `REVIEW`: exige análise de impacto;
- `MIGRATION`: altera schema/dados e requer migração/rollback;
- `DESTRUCTIVE`: pode causar perda de dados ou efeito externo e exige autorização explícita.

Não mascare sintomas. Pergunte se o achado é caso isolado ou classe sistêmica e faça busca global por ocorrências equivalentes.

## 18. Reauditoria contraditória
Após correções, execute regressão e nova rodada tentando provar que as conclusões estão erradas. Não reutilize automaticamente as premissas da primeira passagem. Procure regressões, caminhos equivalentes, serviços secundários, flags, scripts, migrations e integrações pouco usadas.

## 19. Matriz de cobertura obrigatória
Registre no relatório final, para cada área pertinente, `Auditada | Problemas | Corrigidos | Pendentes | Evidência`: backend, frontend, banco, APIs, jobs, queues, cron, webhooks, integrações, segurança, permissões, testes, CI/CD, infraestrutura, logs, monitoramento, backup/restore, UX, performance, dependências e documentação.

Área não auditada deve aparecer explicitamente com motivo. Não esconda lacunas.

## 20. Gate Final de Completude
Não use "100%", "pronto" ou "apto" apenas por build/test/health verde. Antes do veredito valide, conforme aplicável:
- código: build/lint/typecheck/testes;
- dados: integridade/migrations/constraints/estados;
- fluxos: happy path/edge/failure/retry/idempotência;
- integrações: erros/timeout/reconciliação;
- operação: jobs/filas/cron/logs/health/alertas;
- segurança: authn/authz/isolation/secrets;
- produção: versão/configuração/processos/comportamento real;
- recuperação: backup/restore/rollback.

Veredito: `NÃO APTO`, `APTO COM RESSALVAS` ou `APTO`, acompanhado de **confiança 0–100%**, **risco residual** e **dívida de evidência**. Nunca use 100% de confiança com área crítica não validada.

## 21. Meta-auditoria final
Antes de encerrar, responda e investigue:
1. Que classe inteira de falha esta auditoria pode ter esquecido de procurar?
2. Quais conclusões dependem de suposição e não de evidência?
3. Se este relatório estiver errado, onde provavelmente estará errado?
4. Se eu fosse pessoalmente responsável técnica, financeira e operacionalmente por este sistema, o que ainda poderia causar perda financeira, perda de dados, efeito externo incorreto, indisponibilidade ou trabalho manual evitável?

Somente depois dessa rodada finalize e atualize `docs/quality/AUDIT_STATUS.md` com o SHA/release efetivamente coberto.
