# Protocolo IA-to-CLI obrigatório para Codex/OpenAI

Antes de qualquer alteração em código, configuração, documentação versionada ou infraestrutura:
1. leia integralmente `AGENTS.md` (se existir) e siga também todas as instruções por ele referenciadas;
2. leia integralmente `AI-TO-CLI-PROTOCOL.md`;
3. aplique ambos, preservando sempre as regras específicas do projeto.

Este `AGENTS.override.md` existe somente como ponto de entrada para garantir essa leitura; ele não substitui semanticamente a governança de `AGENTS.md`.

Nenhuma alteração válida da tarefa pode ser abandonada sem merge validado na branch de destino.
Regra de continuidade: leia e cumpra `AI-TO-CLI-PROTOCOL.md`, especialmente `Continuidade obrigatoria diante de falha de ferramenta ou comando`; erro de ferramenta nao autoriza encerrar a tarefa.

Antes de finalizar qualquer tarefa, cumpra tambem o `PROTOCOLO OBRIGATORIO DE CONCLUSAO DE TAREFAS` de `AI-TO-CLI-PROTOCOL.md`.

## Gate obrigatório de auditoria
Leia `AUDIT_POLICY.md`. Quando um projeto, módulo ou release for declarado pronto/finalizado/apto para produção, quando houver solicitação de auditoria completa, ou quando ocorrer mudança material definida nessa política, execute integralmente `docs/quality/EXTREME_AUDIT_PROTOCOL.md` e `docs/quality/AUDIT_OVERLAY.md`. Não declare cobertura total com área crítica não validada. Ao concluir auditoria formal, atualize `docs/quality/AUDIT_STATUS.md` com o SHA/release efetivamente coberto e as evidências do Gate Final de Completude.
