# Política Universal de Auditoria

Esta política é obrigatória para qualquer agente humano ou automatizado que trabalhe neste repositório.

**Versão global:** `2026-09-21-absolute-v5`

## Regra permanente
Nenhuma implementação, feature, release ou projeto pode ser declarado concluído apenas porque código foi escrito, build passou ou testes ficaram verdes. Antes da conclusão, devem ser validados comportamento, regressões, integrações afetadas, dados, estados, rotinas automáticas e riscos operacionais pertinentes.

## Regras globais inseparáveis
Toda auditoria formal deve executar como conjunto obrigatório:
- `docs/quality/EXTREME_AUDIT_PROTOCOL.md`;
- `docs/quality/AUDIT_RUNTIME_PARITY_V1.md`;
- `docs/quality/AUDIT_UNIVERSAL_COVERAGE_V1.md`;
- `docs/quality/ARCHITECTURE_DEPLOY_AUDIT_V1.md`;
- `docs/quality/AUDIT_SELF_TEST_V1.md` quando houver mudança material no mecanismo/gate de auditoria ou quando o projeto possuir gates automatizados a certificar;
- `docs/quality/AUDIT_BROWSER_E2E_REAL_V1.md` quando existir UI;
- `docs/quality/AUDIT_JOURNEY_INVENTORY_V1.md`;
- `docs/quality/AUDIT_CLEAN_ROOM_REALITY_V1.md`;
- `docs/quality/AUDIT_HARDENING_MAX_V1.md`;
- `docs/quality/AUDIT_APTO_REMEDIATION_LOOP_V1.md`;
- `docs/quality/AUDIT_ESCAPE_INVALIDATION_V1.md`;
- `docs/quality/AUDIT_ABSOLUTE_GATE_V1.md`;
- `docs/quality/AUDIT_AUTH_CREDENTIAL_DISCOVERY_V1.md`;
- `docs/quality/AUDIT_MERGE_ENFORCEMENT_V1.md`;
- `docs/quality/AUDIT_PROJECT_REQUIREMENTS_V1.md` e `docs/quality/AUDIT_PROJECT_REQUIREMENTS.json` local;
- `docs/quality/AUDIT_OVERLAY.md`.

Nenhum desses documentos isoladamente substitui os demais.

### Enforcement do caminho de merge

Todo repositório governado deve manter `scripts/absolute-audit-governance-validate.sh` e `.github/workflows/absolute-audit-main-guard.yml`. O `governance-gate` local deve chamar o bridge absoluto, preservando checks específicos do projeto. Todo push efetivo para `main`/`master` deve reexecutar o bridge e comprovar associação do commit a PR realmente mesclado pela regra `AUDIT_MERGE_ENFORCEMENT_V1`.

Se ruleset/branch protection não estiver disponível no plano ou não puder ser alterado pela credencial do agente, isso é uma limitação de enforcement da plataforma, não autorização para declarar que push direto está tecnicamente bloqueado. O Main Guard continua obrigatório e falha fechado quando detecta bypass.

### Adaptador local de runner — paridade semântica obrigatória

O workflow `.github/workflows/absolute-audit-governance.yml` é um **adaptador local**, porque os repositórios podem exigir runners/labels diferentes por isolamento operacional. Ele não precisa ser byte-a-byte idêntico ao canônico, mas deve preservar integralmente os gates semânticos exigidos por `GLOBAL_AUDIT_MANIFEST.json|required_entrypoint_markers`: compilação das ferramentas, self-test do certifier, self-test da governança e validação de paridade global. O runner/action version deve respeitar a política local mais restritiva do repositório. Alterar/remover um desses gates bloqueia governança.

### Modo absoluto obrigatório — fail-closed

Toda Auditoria Extrema formal opera em modo absoluto. O objetivo não é produzir relatório: é **corrigir até que o escopo certificado se torne APTO**. Enquanto existir defeito, jornada/estado/controle material não validado, evidência material ausente, erro de runtime, divergência, `AUDIT_ESCAPE`, `IMPROVEMENT_REQUIRED` material ou outro bloqueador executável, `NÃO APTO` é apenas estado intermediário e o agente controlador deve continuar o ciclo de remediação.

O agente não pode autoatribuir `APTO`. O veredito final deve ser calculado por `scripts/certify-audit-manifest.py` a partir de `AUDIT_CERTIFICATION_MANIFEST_V1`; somente `AUDIT_VERDICT=APTO` para o mesmo SHA/release/ambiente/escopo autoriza declarar `APTO`. Campo crítico ausente falha fechado.

No modo absoluto, `APTO COM RESSALVAS` é proibido. O encerramento permitido é somente `APTO` ou `BLOCKED_EXTERNAL`, sendo este último restrito a bloqueio externo real, provado e incontornável com as autorizações/ferramentas disponíveis. Complexidade, duração, quantidade de defeitos, teste manual, limite de subagente ou “pré-existente” não são bloqueios externos.

`APTO` exige zero P0/P1/P2/P3 abertos, zero `DEFECT` aberto, zero `IMPROVEMENT_REQUIRED` aberto, zero `AUDIT_ESCAPE` pendente, zero bloqueador executável, zero superfície/jornada/controle material não mapeado ou não testado e zero dívida de evidência material. P4 `IMPROVEMENT_OPTIONAL` só pode permanecer se não representar risco material, prevenção de recorrência, observabilidade, recuperação, integridade, segurança ou confiabilidade operacional.

Antes de qualquer `BLOCKED_EXTERNAL` por login, sessão, OAuth ou credencial, execute `AUDIT_AUTH_CREDENTIAL_DISCOVERY_V1`: cubra 100% dos repositórios governados, perfis/sessões canônicos, referências de secret stores/runtime e transportes permitidos, sem jamais expor valores. Cada repositório também deve manter `docs/quality/AUDIT_PROJECT_REQUIREMENTS.json`; todos os invariantes locais são gates obrigatórios do certifier.


É proibido declarar `APTO` com fluxo crítico validado apenas localmente ou apenas por carregamento de página/healthcheck. Quando houver UI, operações críticas e mutações devem ser executadas pela UI real contra o mesmo release/ambiente certificado, com reload/revisita e confirmação da persistência/efeito. Quando não houver UI, use a interface operacional canônica publicada.

Em homologação web, `5xx`, `pageerror`, `requestfailed`, `console.error` ou tela de erro inesperados são gate de falha até investigação, salvo allowlist estreita, versionada e justificada. A suíte local e a suíte executada no ambiente publicado devem ser comparadas; fluxo crítico local sem evidência equivalente publicada é dívida de evidência e bloqueia `APTO`.

Defeito descoberto após auditoria que deveria estar no escopo é `AUDIT_ESCAPE`: além de corrigir o defeito, investigue por que a auditoria não o detectou, identifique a classe de falha, procure equivalentes e reaudite essa classe nos demais projetos onde for aplicável. Uma lacuna sistêmica deve atualizar a regra global, não apenas o caso isolado.

## Matriz de transições de estado e dados históricos
A **matriz de transições de estado e dados históricos** é obrigatória para qualquer fluxo persistido ou stateful. A auditoria deve cruzar, conforme aplicável:
1. operação/transição: criar, ler, no-op update, editar campos, cancelar, reabrir, arquivar, restaurar, retry, undo e toda transição de domínio;
2. proveniência/forma do dado: novo/atual, legado/pré-migração, migrado/backfill, parcial/null-edge, snapshot/política/evento versionado, estado intermediário e terminal;
3. superfície: mutações usadas por operador/usuário devem ocorrer pela UI real; API, SQL, scripts e chamadas diretas são apoio, não substituem a prova pela UI;
4. pós-condição: persistência, histórico/audit log, estados dependentes, efeitos externos, idempotência/retry e confirmação após recarregar/reabrir.

Antes de marcar um fluxo como coberto, inventarie no ambiente alvo as classes materiais de estado, versão, nullabilidade e formato histórico realmente existentes. Classe material não exercitada = `NÃO VALIDADO`; happy path em seed atual não certifica compatibilidade histórica.

Quando código atual consome JSON persistido, snapshots, eventos ou estruturas versionadas, prove migração/backfill completo ou normalização explícita das versões históricas suportadas. Type cast não é evidência de compatibilidade.

Qualquer mutação operacional que produza 5xx, tela genérica de erro, `This page couldn’t load`, blank state ou error boundary bloqueia `APTO` até causa raiz, classe de dados afetada, correção e regressão serem comprovadas.

## AUDIT_REMEDIATION_COMPLETENESS_V1 — remediação obrigatória
Auditoria extrema não termina no diagnóstico. Todo achado deve ser classificado quanto à severidade (`P0–P4`), natureza (`DEFECT`, `IMPROVEMENT_REQUIRED` ou `IMPROVEMENT_OPTIONAL`) e modo de correção (`SAFE`, `REVIEW`, `MIGRATION` ou `DESTRUCTIVE`).

- Achado `SAFE` de severidade `P0`, `P1` ou `P2` deve ser corrigido na própria auditoria, com teste antes/depois, regressão e reauditoria. É proibido encerrar apenas registrando problema corrigível.
- Achado `REVIEW`, `MIGRATION` ou `DESTRUCTIVE` deve ter causa raiz, plano executável, pré-condições, owner, risco, evidência do bloqueio e critério de validação. A classificação não pode ser usada para estacionar correção segura.
- `IMPROVEMENT_REQUIRED` é melhoria sem defeito ativo que fecha risco material, lacuna de prevenção, observabilidade, recuperação, idempotência, segurança ou recorrência. Ela integra o gate aplicável.
- `IMPROVEMENT_OPTIONAL` é otimização sem risco material atual e pode permanecer como backlog sem mascarar o estado real.

### Gate de zero pendência crítica
`APTO` exige simultaneamente: `P0=0`; `P1=0`; nenhum `P2` material em fluxo crítico; nenhuma área crítica `NÃO VALIDADO`; nenhum `AUDIT_ESCAPE` aplicável ainda sem causa do falso-negativo, correção e reauditoria; nenhum `IMPROVEMENT_REQUIRED` que seja condição de segurança, integridade, recuperação ou prevenção de recorrência.

`APTO COM RESSALVAS` só pode ser usado para risco residual não crítico e claramente delimitado. Nunca converta `P0/P1`, `P2` crítico, falha de runtime, dívida de evidência crítica ou efeito externo não reconciliado em mera ressalva.

## AUDIT_SYSTEMIC_SEARCH_V1 — busca obrigatória por equivalentes
Para cada defeito confirmado, registre e execute a cadeia `Achado → Classe de falha → Busca global → Ocorrências equivalentes → Correções → Testes → Reauditoria`. Corrigir somente o registro, endpoint, tela ou caso que revelou o problema não encerra o achado quando a mesma classe puder existir em componentes equivalentes.

## AUDIT_OBSERVABILITY_PROOF_V1 — provar que a falha é detectável
Existência de healthcheck, log, alerta, watchdog, dead-letter ou métrica não prova observabilidade. Quando seguro e autorizado, provoque uma falha controlada e demonstre detecção, diagnóstico e recuperação/encaminhamento. Se a injeção não puder ser feita com segurança, registre a limitação como dívida de evidência e use a evidência operacional equivalente mais forte disponível.

## AUDIT_POST_DEPLOY_OBSERVATION_V1 — observar e reconciliar o release real
Quando houver deploy/publicação, a validação não termina no instante em que o release fica ativo. Prove `deploy → processo ativo → operação real → observação → efeito durável → reconciliação`. Workers, filas, schedulers, webhooks e integrações críticas devem ter pelo menos uma execução produção-equivalente comprovada no release certificado, por ciclo natural ou disparo controlado seguro. Falha assíncrona posterior invalida a conclusão incompatível.

## AUDIT_RECOVERY_ROLLBACK_V1 — recuperação e rollback
Quando aplicável, valide compatibilidade de rollback e recuperação: aplicação, schema, filas, eventos, caches e dados persistidos. Mudança crítica deve demonstrar `deploy → operação/mutação → rollback ou restore ensaiado → validação → retomada` em ambiente seguro apropriado. Não execute rollback destrutivo em produção apenas para satisfazer a auditoria; use staging/preview/clone consistente quando o risco assim exigir.

## AUDIT_LEGACY_DUPLICATION_V1 — legado e concorrência operacional
Toda auditoria extrema deve inventariar serviços, processos, timers, cron jobs, schedulers, workflows, runners, scripts operacionais, consumers, bridges e automações que possam executar a mesma responsabilidade. Procure legado ativo, duplicidade, concorrência, polling redundante, job órfão e hotfix fora do fluxo versionado. Um caminho novo correto não é suficiente se um caminho antigo ainda puder produzir efeitos.

## AUDIT_ESCAPE_REGISTER_V1 — memória institucional de falhas escapadas
Todo `AUDIT_ESCAPE` deve ser registrado em `docs/quality/AUDIT_ESCAPE_REGISTER.md` com classe de falha, causa funcional, causa do falso-negativo, superfícies afetadas, prevenção adicionada, projetos onde a classe é aplicável e evidência de reauditoria. Auditorias futuras devem consultar esse registro e testar as classes históricas aplicáveis.

## AUDIT_DEFINITION_OF_DONE_V1 — conclusão objetiva da auditoria
Antes de encerrar uma auditoria formal, prove conforme aplicável:
1. SHA/release/ambiente identificados e artefato publicado comprovado;
2. fluxos críticos e classes históricas materiais inventariados;
3. achados reproduzidos e classificados;
4. correções `SAFE` executadas, sem `P0/P1` ou `P2` crítico pendente;
5. busca sistêmica por equivalentes concluída;
6. testes de prevenção/regressão adicionados ou reforçados;
7. runtime parity e persistência após reload/reopen comprovadas;
8. efeitos externos reconciliados;
9. observabilidade demonstrada para falhas críticas;
10. workers/schedulers/filas/webhooks relevantes observados no release;
11. backup/restore/rollback validados conforme risco;
12. legado/duplicidade operacional inventariados e saneados ou explicitamente classificados;
13. reauditoria contraditória e meta-auditoria concluídas;
14. `AUDIT_STATUS.md` e, quando aplicável, `AUDIT_ESCAPE_REGISTER.md` atualizados;
15. evidência fresca/proveniente do release certificado;
16. mapa de impacto e taxonomia universal revisados;
17. matriz de negativos/boundaries materiais executada;
18. auditoria arquitetural/deploy executada, com caminho crítico e gargalos materiais classificados;
19. reconciliação de dados e detecção de órfãos concluídas;
20. falhas silenciosas e false-green explicitamente investigados;
21. baseline/regressão operacional comparado quando material;
22. owner/deadline/detector definidos para pendências legítimas;
23. pacote de evidência estruturada produzido/atualizado;
24. self-test dos gates executado quando aplicável.

Se qualquer item material aplicável não tiver evidência, o estado continua `NÃO APTO` e o loop de remediação deve prosseguir. Somente bloqueio externo real permite `BLOCKED_EXTERNAL`; nunca conclusão silenciosa.

## AUDIT_UNIVERSAL_COVERAGE_V1 — cobertura aberta de classes de erro
A Auditoria Extrema deve executar `docs/quality/AUDIT_UNIVERSAL_COVERAGE_V1.md`. Essa regra adiciona validade temporal/proveniência da evidência, mapa de impacto, matriz negativa/boundary, reconciliação de dados, detecção de órfãos, falha silenciosa, testes diferenciais/metamórficos, combate a flaky/falso-verde, segurança de efeitos externos, baseline de regressão, ownership/deadline, matriz de ambientes, taxonomia universal, unknown unknowns, propagação cross-repo e pacote estruturado de evidências.

A taxonomia é deliberadamente aberta. Não é permitido interpretar sua lista como enumeração completa dos erros possíveis. Uma rodada exploratória adversarial deve procurar classes não previstas e promover novas classes descobertas à governança futura.

## ARCHITECTURE_DEPLOY_AUDIT_V1 — arquitetura e velocidade também são qualidade
Toda Auditoria Extrema deve executar `docs/quality/ARCHITECTURE_DEPLOY_AUDIT_V1.md`. A auditoria deve reconstruir arquitetura real e avaliar deploy/CI, separação de runners, caminho crítico, build-once/promote, cache, provisionamento/restart por impacto, migrations expand/contract, canary/rollback, workflow sprawl, contratos cross-repo, ownership de dados, config/secrets, hotspots de código, blast radius e proveniência do release.

Melhoria arquitetural material identificada deve ser tratada como `IMPROVEMENT_REQUIRED` quando reduzir risco operacional, fila de deploy, ponto único de falha, acoplamento indevido, retrabalho ou custo recorrente. Arquitetura funcional porém desnecessariamente lenta/frágil não é considerada “sem erro”.

## AUDIT_SELF_TEST_V1 — auditoria que não se testa não certifica
Sempre que a política ou os gates mudarem materialmente, execute `docs/quality/AUDIT_SELF_TEST_V1.md` nos mecanismos automatizados aplicáveis. Deve existir evidência de que falhas deliberadamente injetadas tornam o gate vermelho e de que casos válidos não são reprovados sem motivo.

## Regra contra promessa impossível de cobertura absoluta
O objetivo é maximizar cobertura e reduzir pontos cegos, não afirmar onisciência. É proibido declarar que “qualquer erro possível” foi matematicamente excluído. O que pode ser declarado é que todas as classes materiais conhecidas foram exercitadas, que houve caça adversarial a classes desconhecidas e que a dívida de evidência residual foi explicitada.

## Quando a auditoria extrema é obrigatória
Execute integralmente o conjunto obrigatório de `docs/quality/EXTREME_AUDIT_PROTOCOL.md`, `docs/quality/AUDIT_RUNTIME_PARITY_V1.md`, `docs/quality/AUDIT_UNIVERSAL_COVERAGE_V1.md`, `docs/quality/ARCHITECTURE_DEPLOY_AUDIT_V1.md`, `docs/quality/AUDIT_SELF_TEST_V1.md` quando aplicável e `docs/quality/AUDIT_OVERLAY.md` quando houver qualquer uma destas condições:
- projeto, módulo ou release declarado "pronto", "finalizado", "100%", "apto para produção" ou equivalente;
- solicitação explícita de auditoria, validação completa, revisão extrema ou investigação sistêmica;
- mudança material em autenticação/autorização, schema, regras financeiras, máquina de estados, multi-tenant, integrações externas, workers, filas, cron/scheduler, infraestrutura, deploy, backup/restore ou regras críticas de negócio;
- incidente relevante, regressão sistêmica, `AUDIT_ESCAPE` ou evidência de divergência entre código e produção.

## Princípios
1. O protocolo é piso mínimo, nunca teto. Crie novas categorias de investigação quando o domínio ou as evidências exigirem.
2. Diferencie sempre `COMPROVADO`, `INFERIDO`, `HIPÓTESE A VALIDAR` e `NÃO VALIDADO`.
3. Procure não apenas código incorreto, mas também rotinas ausentes, estados sem saída, produtor sem consumidor, consumidor sem produtor, dados sem reconciliação e operações sem recuperação.
4. Não declare 100% auditado se qualquer área crítica permanecer não validada.
5. Toda auditoria deve estar ligada a um commit/release identificável. Mudança material posterior invalida a cobertura correspondente.
6. Achados críticos devem ser reproduzidos e, quando seguro/autorizado, corrigidos na própria auditoria, testados, regredidos e reauditados; relatório sem remediação não encerra achado corrigível.
7. Produção só é considerada validada quando houver evidência de que o artefato/release auditado é o que realmente está executando.
8. Não faça mudança destrutiva apenas para satisfazer a auditoria; classifique a correção como SAFE, REVIEW, MIGRATION ou DESTRUCTIVE.
9. Happy path em dados recém-criados não certifica compatibilidade histórica nem cobertura de transições.

## Estado e domínio
- Atualize `docs/quality/AUDIT_STATUS.md` ao concluir uma auditoria formal.
- Leia `docs/quality/AUDIT_OVERLAY.md` para regras específicas deste projeto.

## Prompt curto de ativação
Use:

> Execute integralmente `docs/quality/EXTREME_AUDIT_PROTOCOL.md`, `docs/quality/AUDIT_RUNTIME_PARITY_V1.md`, `docs/quality/AUDIT_UNIVERSAL_COVERAGE_V1.md`, `docs/quality/ARCHITECTURE_DEPLOY_AUDIT_V1.md`, `docs/quality/AUDIT_SELF_TEST_V1.md` quando aplicável e `docs/quality/AUDIT_OVERLAY.md`. Assuma Auditor + Consultor + Operador. MAPEAR → IMPACTAR → QUESTIONAR → REPRODUZIR → PROVAR → CLASSIFICAR → CORRIGIR → BUSCAR EQUIVALENTES → RECONCILIAR DADOS → TESTAR → DEPLOYAR → OBSERVAR → RECONCILIAR EFEITOS → REGREDIR → REAUDITAR → AUTO-TESTAR A AUDITORIA → META-AUDITAR. Cubra taxonomia universal, negativos, boundaries, falhas silenciosas, órfãos, drift, flakiness e unknown unknowns; corrija todo achado SAFE executável e só conclua após zero pendência crítica, runtime parity e AUDIT_DEFINITION_OF_DONE_V1.

## EXECUTION_OWNERSHIP_FAILOVER_V1 — supervisao global de subagentes
Toda delegacao para subagente e uma execucao supervisionada. O agente controlador continua sendo o dono da conclusao e deve monitorar a tarefa desde o disparo, registrando identidade da sessao/processo, inicio, estado/commit de base, artefatos esperados e evidencias objetivas de progresso.

Durante a execucao, devem existir checkpoints limitados de progresso. Estar `rodando`, ter PID ou manter uma sessao aberta nao basta: progresso precisa ser comprovado por arquivos, commits, testes, relatorios, acoes concluidas ou evidencia equivalente da tarefa.

Falha, limite, autenticacao/tooling indisponivel, encerramento sem artefatos ou ausencia de progresso acompanhada de evidencia de bloqueio/ociosidade/travamento/timeout exigem takeover automatico: preserve trabalho util e assuma diretamente ou substitua por sessao limpa. O usuario nunca deve precisar enviar `siga`, `continue` ou mensagem equivalente para recuperar a execucao.

### Persistencia de supervisao fora do chat
O estado de monitoramento de subagentes deve ser persistido em arquivo/ledger do projeto e sobreviver a espera, reconexao, verificacoes adicionais, limite ou interrupcao da resposta do ChatGPT.

Indicadores da interface do chat nao contam como evidencia de progresso do subagente. Ao retomar, o controlador deve ler o estado persistido, verificar artefatos/commits/testes/efeitos reais e executar takeover automatico quando os criterios de falha ou estagnacao forem satisfeitos.
