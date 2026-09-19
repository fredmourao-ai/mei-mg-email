# Protocolo IA-to-CLI obrigatório para Codex/OpenAI

Antes de qualquer alteração em código, configuração, documentação versionada ou infraestrutura:
1. leia integralmente `AGENTS.md` (se existir) e siga também todas as instruções por ele referenciadas;
2. leia integralmente `AI-TO-CLI-PROTOCOL.md`;
3. aplique ambos, preservando sempre as regras específicas do projeto.

Este `AGENTS.override.md` existe somente como ponto de entrada para garantir essa leitura; ele não substitui semanticamente a governança de `AGENTS.md`.

Nenhuma alteração válida da tarefa pode ser abandonada sem merge validado na branch de destino.

## Gate obrigatório de auditoria
Leia `AUDIT_POLICY.md`. Quando um projeto, módulo ou release for declarado pronto/finalizado/apto para produção, quando houver solicitação de auditoria completa, ou quando ocorrer mudança material definida nessa política, execute integralmente `docs/quality/EXTREME_AUDIT_PROTOCOL.md`, `docs/quality/AUDIT_RUNTIME_PARITY_V1.md`, `docs/quality/AUDIT_UNIVERSAL_COVERAGE_V1.md`, `docs/quality/ARCHITECTURE_DEPLOY_AUDIT_V1.md`, `docs/quality/AUDIT_SELF_TEST_V1.md` quando aplicável e `docs/quality/AUDIT_OVERLAY.md`. Auditoria extrema inclui remediar achados SAFE, buscar equivalentes, reconciliar dados, testar negativos/boundaries, procurar falhas silenciosas/órfãos/flaky/unknown unknowns, auditar arquitetura/deploy/código e gargalos, provar runtime/observabilidade/recuperação e cumprir o gate de zero pendência crítica; relatório de problemas não é conclusão. Ao concluir auditoria formal, atualize `docs/quality/AUDIT_STATUS.md` e registre `AUDIT_ESCAPE` em `docs/quality/AUDIT_ESCAPE_REGISTER.md`.
