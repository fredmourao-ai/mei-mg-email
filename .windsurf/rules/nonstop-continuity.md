# Continuidade obrigatoria

Leia `AGENTS.md` e `AI-TO-CLI-PROTOCOL.md`. A regra `Continuidade obrigatoria diante de falha de ferramenta ou comando` e vinculante para todos os agentes. Erro de tool/CLI/API nao encerra a tarefa; use fallback seguro, mantenha estado recuperavel e continue ate conclusao validada ou bloqueio externo real.
