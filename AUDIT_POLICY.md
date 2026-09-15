# Política Universal de Auditoria

Esta política é obrigatória para qualquer agente humano ou automatizado que trabalhe neste repositório.

## Regra permanente
Nenhuma implementação, feature, release ou projeto pode ser declarado concluído apenas porque código foi escrito, build passou ou testes ficaram verdes. Antes da conclusão, devem ser validados comportamento, regressões, integrações afetadas, dados, estados, rotinas automáticas e riscos operacionais pertinentes.

## Quando a auditoria extrema é obrigatória
Execute integralmente `docs/quality/EXTREME_AUDIT_PROTOCOL.md` quando houver qualquer uma destas condições:
- projeto, módulo ou release declarado "pronto", "finalizado", "100%", "apto para produção" ou equivalente;
- solicitação explícita de auditoria, validação completa, revisão extrema ou investigação sistêmica;
- mudança material em autenticação/autorização, schema, regras financeiras, máquina de estados, multi-tenant, integrações externas, workers, filas, cron/scheduler, infraestrutura, deploy, backup/restore ou regras críticas de negócio;
- incidente relevante, regressão sistêmica ou evidência de divergência entre código e produção.

## Princípios
1. O protocolo é piso mínimo, nunca teto. Crie novas categorias de investigação quando o domínio ou as evidências exigirem.
2. Diferencie sempre `COMPROVADO`, `INFERIDO`, `HIPÓTESE A VALIDAR` e `NÃO VALIDADO`.
3. Procure não apenas código incorreto, mas também rotinas ausentes, estados sem saída, produtor sem consumidor, consumidor sem produtor, dados sem reconciliação e operações sem recuperação.
4. Não declare 100% auditado se qualquer área crítica permanecer não validada.
5. Toda auditoria deve estar ligada a um commit/release identificável. Mudança material posterior invalida a cobertura correspondente.
6. Achados críticos devem ser reproduzidos e, quando seguro/autorizado, corrigidos, testados, regredidos e reauditados.
7. Produção só é considerada validada quando houver evidência de que o artefato/release auditado é o que realmente está executando.
8. Não faça mudança destrutiva apenas para satisfazer a auditoria; classifique a correção como SAFE, REVIEW, MIGRATION ou DESTRUCTIVE.

## Estado e domínio
- Atualize `docs/quality/AUDIT_STATUS.md` ao concluir uma auditoria formal.
- Leia `docs/quality/AUDIT_OVERLAY.md` para regras específicas deste projeto.

## Prompt curto de ativação
Use:

> Execute integralmente `docs/quality/EXTREME_AUDIT_PROTOCOL.md` e `docs/quality/AUDIT_OVERLAY.md`. Assuma as lentes Auditor + Consultor + Operador. Não limite a investigação às alterações recentes. Reconstrua o sistema real, procure bugs e rotinas ausentes, acompanhe fluxos ponta a ponta, valide dados/produção quando aplicável, corrija o que for seguro, execute regressão e só conclua após o Gate Final de Completude. Diferencie COMPROVADO, INFERIDO, HIPÓTESE A VALIDAR e NÃO VALIDADO.
