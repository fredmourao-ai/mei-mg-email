<!-- RESUME_EXECUTION_GATE_V1 -->
## Retome / Continue / Prossiga / Siga: execucao obrigatoria ate verificacao

Toda ordem Retome, Continue, Prossiga ou Siga e uma tarefa operacional de execucao, nao pedido de plano, status ou confirmacao generica. O agente principal, Claude, Gemini, Copilot e qualquer subagente devem ler as regras atuais do AGENTS.md no main e registrar prova nao secreta rules_loaded (fonte, ref, SHA, data) antes de mutacoes. Recuperar task_id, ultimo checkpoint e next_action com origem real; nao criar identidades de conversa ou sessoes ficticias.
Executar a proxima acao permitida; investigar erro, corrigir a causa, testar, fazer merge/deploy quando autorizado e validar o objetivo original no runtime. Persistir RUNNING com next_action real enquanto houver caminho seguro viavel; erro de ferramenta, timeout, status Pensando, PR ou ACK nao autorizam encerrar. CONCLUIDO exige evidencia fresca ponta a ponta; BLOCKED_EXTERNAL exige impedimento externo objetivo, alternativas seguras esgotadas e condicao exata de retomada. Quando disponivel, comprovar terminalidade com agent_task_state.py terminal --task <task_id>.
Nao contornar MFA, RBAC, aprovacao sensivel, branch protection ou direitos de outra sessao. Evitar mensagens intermediarias desnecessarias quando o proprietario pedir para nao postar; se limite externo interromper a execucao, salvar checkpoint verdadeiro e nao prometer trabalho de fundo sem mecanismo realmente ativo. Encaminhar as mesmas obrigacoes ao agente delegado.
<!-- /RESUME_EXECUTION_GATE_V1 -->

# GitHub Copilot / coding agents

Antes de qualquer trabalho, leia e cumpra `AGENTS.md` e `AI-TO-CLI-PROTOCOL.md`. A secao `Continuidade obrigatoria diante de falha de ferramenta ou comando` e vinculante: uma falha de CLI/API/tool nao encerra a tarefa; diagnostique, use fallback seguro, persista checkpoint e continue ate CONCLUIDO ou bloqueio externo real.
