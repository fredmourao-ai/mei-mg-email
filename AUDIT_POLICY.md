# Política Universal de Auditoria

Esta política é obrigatória para qualquer agente humano ou automatizado que trabalhe neste repositório.

**Versão global:** `2026-09-16-historical-state-transition-v2`

## Regra permanente
Nenhuma implementação, feature, release ou projeto pode ser declarado concluído apenas porque código foi escrito, build passou ou testes ficaram verdes. Antes da conclusão, devem ser validados comportamento, regressões, integrações afetadas, dados, estados, rotinas automáticas e riscos operacionais pertinentes.

## AUDIT_RUNTIME_PARITY_V1 — regra global obrigatória
Toda auditoria formal deve executar também `docs/quality/AUDIT_RUNTIME_PARITY_V1.md` como complemento obrigatório e inseparável de `docs/quality/EXTREME_AUDIT_PROTOCOL.md`.

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

## Quando a auditoria extrema é obrigatória
Execute integralmente `docs/quality/EXTREME_AUDIT_PROTOCOL.md` **e** `docs/quality/AUDIT_RUNTIME_PARITY_V1.md` quando houver qualquer uma destas condições:
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
6. Achados críticos devem ser reproduzidos e, quando seguro/autorizado, corrigidos, testados, regredidos e reauditados.
7. Produção só é considerada validada quando houver evidência de que o artefato/release auditado é o que realmente está executando.
8. Não faça mudança destrutiva apenas para satisfazer a auditoria; classifique a correção como SAFE, REVIEW, MIGRATION ou DESTRUCTIVE.
9. Happy path em dados recém-criados não certifica compatibilidade histórica nem cobertura de transições.

## Estado e domínio
- Atualize `docs/quality/AUDIT_STATUS.md` ao concluir uma auditoria formal.
- Leia `docs/quality/AUDIT_OVERLAY.md` para regras específicas deste projeto.

## Prompt curto de ativação
Use:

> Execute integralmente `docs/quality/EXTREME_AUDIT_PROTOCOL.md`, `docs/quality/AUDIT_RUNTIME_PARITY_V1.md` e `docs/quality/AUDIT_OVERLAY.md`. Assuma Auditor + Consultor + Operador. Reconstrua o sistema real, inventarie dados atuais/legados/migrados, compare cobertura local e publicada, execute operações críticas pela interface canônica no release certificado, trate erros inesperados de runtime como gate, confirme persistência após reload/reopen, corrija o seguro, execute regressão e reauditoria contraditória e só conclua após o Gate Final de Completude. Diferencie COMPROVADO, INFERIDO, HIPÓTESE A VALIDAR e NÃO VALIDADO.
