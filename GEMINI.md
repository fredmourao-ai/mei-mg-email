<!-- SHOPVIVALIZ_HOST_ACCESS_CANONICAL_V2 -->
## Acesso canônico aos hosts ShopVivaliz
Leia `docs/HOST-ACCESS.md` antes de operar host/VM/runtime/browser/serviço/deploy/logs/recuperação. Fonte central: `Vivaliz-site/site-shopvivaliz:docs/knowledge/host-access.md`.
Produção: `shopvivaliz-free-a1/10.0.1.112`; backend/controller/browser: `always-free-arm-1787907847-26/10.0.1.38`; browser somente no backend; Linux por SSH privado/Tailscale; OCI Bastion para bootstrap/recovery; RustDesk GUI; Desktop Commander contingência; Fred-Win via `127.0.0.1:2222`; KOCEPSV via `127.0.0.1:2223`; `5557/5558` só bootstrap/recovery. Validar hostname/identidade/diretório/Git e nunca registrar valores secretos.
<!-- /SHOPVIVALIZ_HOST_ACCESS_CANONICAL_V2 -->

<!-- GEMINI_READ_AGENTS_FIRST_V1 -->
> **BOOTSTRAP OBRIGATÓRIO DO GEMINI:** antes de analisar, planejar, editar, executar comandos, usar navegador, abrir PR, fazer merge, deploy ou validar qualquer tarefa, leia integralmente o `AGENTS.md` da raiz deste repositório e siga suas regras. Releia em retomadas ou quando o arquivo mudar. Em conflito, `AGENTS.md` prevalece.

# Protocolo IA-to-CLI obrigatório

<!-- GLOBAL_BROWSER_VM_POLICY_V2 -->
> **NAVEGAÇÃO GLOBAL — VM OBRIGATÓRIA; WINDOWS PROIBIDO PARA BROWSER:** qualquer navegador, automação browser, sessão gráfica, Playwright/Selenium/CDP, Chrome/Chromium/Edge/Opera, CAPTCHA, MFA, consentimento ou validação visual deve usar por padrão e obrigatoriamente a VM backend `always-free-arm-1787907847-26` (`10.0.1.38`) e o Browser Worker privado. Para intervenção humana, usar `https://shopvivaliz.com.br/admin/browser-worker.php`. **Fred-Win (`LAPTOP-NIG4IFUU`) e `DESKTOP-KOCEPSV` não são destinos nem fallback para navegação.** Não perguntar qual máquina usar para browser: use a VM. Exceção somente se o proprietário ordenar explicitamente, na tarefa atual, o uso de um Windows específico para aquela navegação. Se a VM estiver indisponível, reparar o caminho VM/OCI Bastion/túnel privado ou registrar bloqueio real; nunca migrar silenciosamente para Windows. Workflows/relays Windows de browser são legado e não devem ser executados até serem migrados. A regra não proíbe Windows para tarefas não-browser que realmente dependam dele.


Antes de qualquer alteração, carregue e siga integralmente o protocolo canônico:

@./AI-TO-CLI-PROTOCOL.md

Ele complementa as regras específicas do projeto. Nenhuma alteração válida da tarefa pode ser abandonada sem merge validado na branch de destino.
Regra de continuidade: leia e cumpra `AI-TO-CLI-PROTOCOL.md`, especialmente `Continuidade obrigatoria diante de falha de ferramenta ou comando`; erro de ferramenta nao autoriza encerrar a tarefa.

Antes de finalizar qualquer tarefa, cumpra o `PROTOCOLO OBRIGATORIO DE CONCLUSAO DE TAREFAS` de `AI-TO-CLI-PROTOCOL.md`; nao pare em erro corrigivel ou resultado parcial.

<!-- EXECUTION_PROVENANCE_POLICY_V1 -->
Leia e cumpra EXECUTION-PROVENANCE-POLICY.md antes de qualquer execucao material.

<!-- GLOBAL_TASK_CONTINUITY_V8 -->
## Global task continuity V8
Toda tarefa que possa alterar código, infraestrutura, dados, CI ou deploy deve manter checkpoint durável via `python3 scripts/agent_task_state.py`. Este repositório é fixado como `repository=fredmourao-ai/mei-mg-email`. Falhas recuperáveis permanecem RUNNING e conclusão exige verificação fresca. O adapter falha fechado sem o controlador canônico injetado pelo runtime detached. Background recovery permanece Gemini-only; Codex nunca é fallback automático e continua sendo a última opção finita explícita.
<!-- /GLOBAL_TASK_CONTINUITY_V8 -->
