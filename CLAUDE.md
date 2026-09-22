<!-- GEPETO_EVERY_TASK_V1 -->
## Gepeto obrigatorio em toda tarefa
Acione o plugin Gepeto junto com Superpowers em toda tarefa e retomada, sem nova mencao do usuario. Leia e cumpra a secao `GEPETO_EVERY_TASK_V1` de `REGRAS-AGENTES-CENTRALIZADAS.md`. Se o runtime nao expuser o plugin, registre `GEPETO_UNAVAILABLE`, informe a limitacao e continue o trabalho autorizado sem simular participacao. Aplicar um plugin nao comprova delegacao nem revisao independente.
<!-- /GEPETO_EVERY_TASK_V1 -->

<!-- CLAUDE_READ_AGENTS_FIRST_V1 -->
> **BOOTSTRAP OBRIGATORIO DO CLAUDE:** antes de analisar, planejar, editar, executar comandos, usar navegador, abrir PR, fazer merge, deploy ou validar qualquer tarefa, leia **integralmente** o `AGENTS.md` da raiz deste repositorio e cumpra todas as instrucoes vigentes nele. Releia o `AGENTS.md` em retomadas de conversa ou quando o arquivo mudar. Se houver divergencia entre este `CLAUDE.md` e o `AGENTS.md`, o `AGENTS.md` prevalece. Nao prossiga assumindo memoria de uma leitura antiga.

@AGENTS.md

# Instrucoes para Claude

<!-- GLOBAL_BROWSER_VM_POLICY_V2 -->
> **NAVEGAÇÃO GLOBAL — VM OBRIGATÓRIA; WINDOWS PROIBIDO PARA BROWSER:** qualquer navegador, automação browser, sessão gráfica, Playwright/Selenium/CDP, Chrome/Chromium/Edge/Opera, CAPTCHA, MFA, consentimento ou validação visual deve usar por padrão e obrigatoriamente a VM backend `always-free-arm-1787907847-26` (`10.0.1.38`) e o Browser Worker privado. Para intervenção humana, usar `https://shopvivaliz.com.br/admin/browser-worker.php`. **Fred-Win (`LAPTOP-NIG4IFUU`) e `DESKTOP-KOCEPSV` não são destinos nem fallback para navegação.** Não perguntar qual máquina usar para browser: use a VM. Exceção somente se o proprietário ordenar explicitamente, na tarefa atual, o uso de um Windows específico para aquela navegação. Se a VM estiver indisponível, reparar o caminho VM/OCI Bastion/túnel privado ou registrar bloqueio real; nunca migrar silenciosamente para Windows. Workflows/relays Windows de browser são legado e não devem ser executados até serem migrados. A regra não proíbe Windows para tarefas não-browser que realmente dependam dele.


<!-- audit-refs: AUDIT_POLICY.md docs/quality/EXTREME_AUDIT_PROTOCOL.md docs/quality/AUDIT_RUNTIME_PARITY_V1.md docs/quality/AUDIT_UNIVERSAL_COVERAGE_V1.md docs/quality/ARCHITECTURE_DEPLOY_AUDIT_V1.md docs/quality/AUDIT_SELF_TEST_V1.md -->


<!-- SUPERPOWERS_EVERY_STAGE_V1 -->
> **@Superpowers CONTÍNUO E OBRIGATÓRIO:** toda conversa, sessão, agente e retomada de tarefa destes projetos deve usar @Superpowers **em cada etapa material**, não apenas no início. Reaplique a disciplina adequada ao passar por bootstrap/contexto, planejamento, investigação, coleta de evidências, implementação, debugging, TDD/testes, revisão, correção, PR/checks/merge, deploy, pós-deploy, auditoria e encerramento. Em `retome/continue/prossiga`, continue do último checkpoint comprovado sob @Superpowers. Se o runtime não expuser @Superpowers, registre `SUPERPOWERS_UNAVAILABLE` e aplique a metodologia equivalente sem fingir a chamada. Subagentes e automações delegadas herdam esta obrigação. Fonte local: `REGRAS-AGENTES-CENTRALIZADAS.md`; fonte canônica global: `Vivaliz-site/site-shopvivaliz`.

Antes de qualquer trabalho neste repositorio, leia e cumpra `AGENTS.md` e `AI-TO-CLI-PROTOCOL.md`. A regra `Isolamento obrigatorio de sessao CLI por chat` e vinculante: este chat nao pode reutilizar sessao CLI pertencente a outro chat.
Regra de continuidade: leia e cumpra `AI-TO-CLI-PROTOCOL.md`, especialmente `Continuidade obrigatoria diante de falha de ferramenta ou comando`; erro de ferramenta nao autoriza encerrar a tarefa.

Antes de finalizar qualquer tarefa, cumpra o `PROTOCOLO OBRIGATORIO DE CONCLUSAO DE TAREFAS` de `AI-TO-CLI-PROTOCOL.md`; nao pare em erro corrigivel ou resultado parcial.

<!-- EXECUTION_PROVENANCE_POLICY_V1 -->
@EXECUTION-PROVENANCE-POLICY.md


<!-- BROWSER_SESSION_POLICY_V1 -->
Leia e cumpra AGENTS.md e a secao BROWSER_SESSION_POLICY_V1 de REGRAS-AGENTES-CENTRALIZADAS.md antes de qualquer uso de navegador.


<!-- AUDIT_ABSOLUTE_V5_ENTRYPOINT -->
Leia primeiro `AGENTS.md`. Para auditoria/aptidão, cumpra `AUDIT_ABSOLUTE_GATE_V1.md`, `AUDIT_BROWSER_E2E_REAL_V1.md`, `AUDIT_AUTH_CREDENTIAL_DISCOVERY_V1.md`, `AUDIT_PROJECT_REQUIREMENTS_V1.md` e o manifesto local de requisitos. Somente o certifier pode autorizar APTO.


<!-- AUDIT_MERGE_ENFORCEMENT_V1 -->
<!-- audit-refs: AGENTS.md docs/quality/AUDIT_ABSOLUTE_GATE_V1.md docs/quality/AUDIT_BROWSER_E2E_REAL_V1.md docs/quality/AUDIT_AUTH_CREDENTIAL_DISCOVERY_V1.md docs/quality/AUDIT_MERGE_ENFORCEMENT_V1.md docs/quality/AUDIT_PROJECT_REQUIREMENTS_V1.md -->
