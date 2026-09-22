# AUDIT_ESCAPE_INVALIDATION_V1 — Escape invalida certificação e vira prevenção permanente

Um defeito encontrado depois de uma certificação `APTO` que estava dentro do escopo material é prova de que a certificação anterior era incompleta.

## Invalidação imediata

Ao confirmar um `AUDIT_ESCAPE`:
1. marque a certificação afetada como `INVALIDATED_BY_AUDIT_ESCAPE`;
2. o escopo afetado deixa de ser `APTO` imediatamente;
3. reproduza a falha no release pertinente;
4. identifique causa funcional e causa do falso-negativo da auditoria;
5. corrija pelo `AUDIT_APTO_REMEDIATION_LOOP_V1`;
6. procure equivalentes;
7. adicione prevenção automatizada;
8. reexecute E2E e contraditório;
9. emita **nova** certificação; nunca “reative” a antiga.

## Aprendizado obrigatório

Todo escape aplicável deve produzir pelo menos um dos seguintes:
- teste de regressão;
- fixture de self-test;
- detector/alerta;
- nova regra/invariante;
- ampliação do inventário de jornadas;
- correção do certifier/gate.

Se não houver prevenção reproduzível, o escape continua pendente.

## Métrica de confiabilidade

Mantenha por projeto/release:
- `audit_escape_count`;
- `post_certification_defect_count`;
- `escape_classes`;
- `time_to_detection`;
- `time_to_prevention`.

Escape recorrente da mesma classe é finding do **sistema de auditoria**, não apenas do produto.

## Regra anti-reclassificação

Não é permitido evitar a invalidação alegando que o erro era “pré-existente”, “raro”, “manual”, “de UX” ou “fora do happy path” se ele estava dentro da superfície/jornada material que a certificação dizia cobrir.

**Marker de governança:** `AUDIT_ESCAPE_INVALIDATION_V1`
