# AUDIT_HARDENING_MAX_V1 — Hardening máximo de certificação

Este documento adiciona gates fail-closed para reduzir falsos-verdes que sobrevivem a testes tradicionais.

## 1. CONFIG_RELEASE_FINGERPRINT_V1

A certificação deve registrar um fingerprint reprodutível do ambiente material:
- commit SHA;
- build/artifact digest;
- release ativa;
- schema/migration version;
- feature flags materiais;
- versões de runtime relevantes;
- identificadores não secretos de config/providers.

Mudança material em qualquer componente invalida a certificação afetada até reauditoria. Certificação nunca vale genericamente para “o sistema”; vale para `escopo + fingerprint + ambiente`.

## 2. DUAL_ORACLE_RECONCILIATION_V1

Toda mutação crítica pela UI deve ser confirmada por pelo menos um oracle independente:
- UI após reload/revisita; e
- backend/API/banco/provider/event log/ledger, conforme o domínio.

Quando houver efeito externo, a confirmação deve vir do destino/provedor ou de reconciliação independente, não apenas do request de origem.

Divergência entre oracles = finding e bloqueia `APTO`.

## 3. ROLE_TENANT_STATE_MATRIX_V1

Para fluxos com auth, permissões, multi-tenant ou estados diferentes, derive matriz explícita:
`role × tenant/owner × estado × operação × resultado esperado`.

Classes materiais não exercitadas ficam `NÃO VALIDADO`. Testar somente admin/superuser não certifica usuários comuns ou isolamento.

## 4. CHAOS_RECOVERY_V1

Quando seguro, injete falhas controladas em staging/clone/fixture:
- timeout;
- 429;
- 5xx;
- perda de conexão;
- restart de worker;
- resposta parcial/malformada;
- storage/quota simulados;
- duplicate/out-of-order event.

Prove retry, idempotência, compensação, watchdog, alerta e recuperação. Quando a injeção não for segura em produção, use ambiente equivalente e revalide o caminho publicado sem a falha.

## 5. ASYNC_SETTLEMENT_V1

Fluxos assíncronos não podem ser certificados no instante do clique. Defina condição terminal/settlement por domínio e observe até:
- conclusão/reconciliação; ou
- timeout operacional explícito que gere finding/owner.

`queued`, `accepted`, `processing` ou HTTP 2xx não são estados terminais por si só.

## 6. VISUAL_INTERACTION_REGRESSION_V1

Para UI material, capture evidência antes/depois suficiente para detectar:
- botão invisível/desabilitado;
- overlay interceptando clique;
- campo sem foco/submit;
- layout quebrado em viewport material;
- mensagem de sucesso ausente/enganosa;
- modal/redirect incorreto;
- estado visual divergente do estado real.

Screenshot isolado não basta: associe imagem/trace à ação e à pós-condição.

## 7. CERTIFICATION_INVALIDATION_V1

Uma certificação é automaticamente inválida quando ocorrer qualquer um:
- novo commit material no escopo;
- novo deploy/release;
- migration/schema relevante;
- feature flag/config material alterada;
- provider/API version material alterada;
- `AUDIT_ESCAPE`;
- incidente real contradizendo a certificação;
- mudança no próprio gate/certifier usado.

A nova versão precisa de evidência fresca. Não herde `APTO` por proximidade temporal.

## 8. EVIDENCE_INTEGRITY_V1

O pacote final deve possuir manifesto com hashes dos artefatos de evidência (trace, vídeo, screenshots, logs sanitizados, relatórios). Evidência deve ser imutável/versionada e vinculada ao audit_id.

Arquivo ausente, hash divergente ou artefato de outro release invalida a evidência.

## 9. NO_SELF_ATTESTATION_V1

O agente não pode tornar verdadeiro um requisito apenas escrevendo `true` no manifesto. Campos críticos devem apontar para `evidence_refs` e, quando automatizáveis, ser derivados pelo certifier ou validador.

Para jornadas críticas, o revisor contraditório deve ser distinto do auditor principal.

## 10. STOP_ON_NEW_EVIDENCE_V1

Qualquer erro novo encontrado durante correção, pós-deploy, observação ou contraditório reabre o loop de remediação. Não existe “erro descoberto tarde demais para entrar na rodada”.

**Marker de governança:** `AUDIT_HARDENING_MAX_V1`
