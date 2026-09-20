# Regras obrigatorias para agentes

<!-- GLOBAL_BROWSER_VM_POLICY_V2 -->
> **NAVEGAÇÃO GLOBAL — VM OBRIGATÓRIA; WINDOWS PROIBIDO PARA BROWSER:** qualquer navegador, automação browser, sessão gráfica, Playwright/Selenium/CDP, Chrome/Chromium/Edge/Opera, CAPTCHA, MFA, consentimento ou validação visual deve usar por padrão e obrigatoriamente a VM backend `always-free-arm-1787907847-26` (`10.0.1.38`) e o Browser Worker privado. Para intervenção humana, usar `https://shopvivaliz.com.br/admin/browser-worker.php`. **Fred-Win (`LAPTOP-NIG4IFUU`) e `DESKTOP-KOCEPSV` não são destinos nem fallback para navegação.** Não perguntar qual máquina usar para browser: use a VM. Exceção somente se o proprietário ordenar explicitamente, na tarefa atual, o uso de um Windows específico para aquela navegação. Se a VM estiver indisponível, reparar o caminho VM/OCI Bastion/túnel privado ou registrar bloqueio real; nunca migrar silenciosamente para Windows. Workflows/relays Windows de browser são legado e não devem ser executados até serem migrados. A regra não proíbe Windows para tarefas não-browser que realmente dependam dele.

<!-- FINAL_RESPONSE_DEPLOY_GATE_V1 -->
> **CONCLUSAO GLOBAL — MERGE NAO ENCERRA A TAREFA:** toda alteracao versionada deve seguir ate branch -> validacao -> PR -> checks -> merge e, quando o repositorio tiver alvo de deploy/runtime, deploy pelo gate canonico + validacao pos-deploy real. PR aberta, checks verdes ou merge isoladamente sao estados intermediarios. Antes de responder CONCLUIDO, o agente deve provar que o ramo alvo e o runtime/deploy aplicavel estao na revisao esperada e que nao restou PR da propria rodada. Se o deploy automatico pular, falhar ou ficar atrasado, o agente deve acionar o gate canonico e continuar ate paridade; so um bloqueio externo real e incontornavel permite encerrar como BLOQUEIO EXTERNO/INCONCLUSIVO.



<!-- SUPERPOWERS_EVERY_STAGE_V1 -->
> **@Superpowers CONTÍNUO E OBRIGATÓRIO:** toda conversa, sessão, agente e retomada de tarefa destes projetos deve usar @Superpowers **em cada etapa material**, não apenas no início. Reaplique a disciplina adequada ao passar por bootstrap/contexto, planejamento, investigação, coleta de evidências, implementação, debugging, TDD/testes, revisão, correção, PR/checks/merge, deploy, pós-deploy, auditoria e encerramento. Em `retome/continue/prossiga`, continue do último checkpoint comprovado sob @Superpowers. Se o runtime não expuser @Superpowers, registre `SUPERPOWERS_UNAVAILABLE` e aplique a metodologia equivalente sem fingir a chamada. Subagentes e automações delegadas herdam esta obrigação. Fonte local: `REGRAS-AGENTES-CENTRALIZADAS.md`; fonte canônica global: `Vivaliz-site/site-shopvivaliz`.

Este repositorio opera envio de primeiro contato em lote. Agentes, automacoes, PR-healers e scripts autonomos NAO podem alterar a politica de elegibilidade sem aprovacao explicita do usuario.

## Gate obrigatorio de Auditoria Extrema
Leia `AUDIT_POLICY.md` e execute o conjunto global inseparavel quando houver gatilho de auditoria: `docs/quality/EXTREME_AUDIT_PROTOCOL.md`, `docs/quality/AUDIT_RUNTIME_PARITY_V1.md`, `docs/quality/AUDIT_UNIVERSAL_COVERAGE_V1.md`, `docs/quality/ARCHITECTURE_DEPLOY_AUDIT_V1.md`, `docs/quality/AUDIT_SELF_TEST_V1.md` quando aplicavel e `docs/quality/AUDIT_OVERLAY.md`. O self-test local e `python3 scripts/validate-audit-governance.py`.

## Acesso a infraestrutura e VMs
Antes de executar qualquer comando em VM Oracle Cloud, leia e siga obrigatoriamente [`AGENTS-VM-ACCESS.md`](AGENTS-VM-ACCESS.md). O fluxo canonico e Remote Desktop Commander -> SSH validado -> OCI Compute Instance Run Command pelo perfil `AGENTS` -> serial console como ultimo recurso. Nunca versione credenciais nem presuma root no Run Command.

## Politica atual de exclusao
Os **unicos filtros de negocio/segmentacao** que excluem destinatarios da fila ou do envio sao:
- empresa com situacao cadastral diferente de ATIVA;
- email contendo a palavra `contabil`;
- email compartilhado por mais de 2 cadastros;
- destinatario/CNPJ ja enviado ou ja enfileirado.

Protecoes tecnicas obrigatorias **nao sao filtros de negocio novos** e devem permanecer fail-closed: email ausente/invalido, opt-out, suppression tecnica e divergencia entre o email atual da empresa e o email enfileirado. Elas protegem consentimento, entregabilidade, integridade e anti-replay; nao autorizam reintroduzir criterios antigos de classificacao comercial.

MG e apenas prioridade de ordenacao, nunca filtro de elegibilidade.
## Campos e gates proibidos no fluxo operacional
Nao reintroduzir campos legados de autorizacao comercial, `mei_verificado*`, `tipo_regime`, `vw_empresas_elegiveis`, `filter_not_mei`, `insert_filter_gate` nem filtro `uf='MG'`.

Nao criar nova view, trigger, migration, guard, gate ou supervisor que reproduza essas regras sob outro nome.

## Protecao obrigatoria
Antes de commit, push, merge, deploy ou restart execute:
`python3 scripts/repo_policy_guard.py`

Se o guard falhar, NAO contorne, NAO edite a lista de proibicoes e NAO force o servico a iniciar. Corrija a regressao.
## Regras de alteracao
- Nao executar `git reset --hard`, checkout destrutivo ou `git pull` que sobrescreva mudancas locais de producao sem revisar diff e rodar o guard.
- Nao religar agentes autonomos durante manutencao do repositorio.
- Nao remover opt-out ou suppressions tecnicas sem revisao especifica.
- Nao alterar a meta de fila 14.800-15.000 sem aprovacao explicita.
- Preserve anti-reenvio e idempotencia entre provedores; uma submissao anterior nunca pode ser reenviada por troca de provider.

## Politica obrigatoria de consumo de IA e execucao recorrente
- Claude, GPT/OpenAI e Codex pagos sao permitidos somente em tarefas finitas e devem encerrar quando a tarefa concluir ou atingir bloqueio real.
- E proibido usar IA paga em daemon, service loop, cron/timer periodico, watcher, autorepair, supervisor, polling ou retry sem limite.
- Rotinas permanentes ou periodicas devem ser deterministicas. Se IA for indispensavel, usar opcao gratuita/local aprovada, com limite de chamadas e sem fallback silencioso para provedor pago.
- Toda tarefa finita com IA paga deve ter circuit breaker: timeout, limite de retries/chamadas, condicao de saida e checkpoint quando necessario. Atingido o limite, encerrar em vez de relancar automaticamente.
- Auditar consumidor por consumidor antes de manter ou habilitar automacao: necessidade real, host, gatilho, frequencia, provedor/modelo, custo, timeout, retries, limite de chamadas, condicao de saida e duplicidade/orfandade.
- Processos travados, orfaos ou sem progresso devem ser encerrados e ter a causa raiz investigada. Reinicio infinito e proibido.
- Workflows GitHub com IA paga devem exigir gatilho explicito/restrito; eventos genericos e `schedule` nao podem disparar Claude/GPT/Codex automaticamente.
- Para este repositorio, worker, monitor, NDR guard, queue replenisher, base sync e autorepair devem permanecer deterministas e nao podem adquirir dependencia de IA paga.
- Teste de credencial nao deve gerar conteudo em modelo pago quando validacao de configuracao/formato for suficiente.
- Registrar sem secrets o inicio/fim, gatilho, provedor/modelo, tentativas, duracao e resultado de qualquer consumidor de IA.

## Politica obrigatoria de PR, gate e merge
- Toda alteracao finalizada deve terminar em PR validado e merge; nao deixar PR pronta aberta sem motivo tecnico comprovado.
- Se qualquer check, teste, lint, gate, conflito ou Action falhar: investigar a causa raiz, corrigir, executar novamente e repetir ate ficar verde. E proibido contornar o erro com bypass, `|| true`, `exit 0`, force merge ou desativacao do check.
- Gate verde autoriza merge automatico quando a PR pertence a este repositorio e todas as protecoes aplicaveis passaram.
- Bloqueio aparentemente externo nao encerra a tarefa: procurar solucao segura por configuracao, credencial, permissao, servico, infraestrutura ou rota alternativa antes de classificar como inconclusivo.
- Para este repositorio, auto-gate/auto-merge NUNCA significa disparar campanha, aumentar ritmo de envio, remover supressoes ou alterar elegibilidade. Envios continuam sujeitos aos controles operacionais e de seguranca existentes.
- Depois do merge, verificar Actions do SHA resultante e corrigir falhas regressivas antes de declarar conclusao.

O arquivo `AGENTS.md` e parte da politica do repositorio e deve ser lido antes de qualquer alteracao automatizada.

## Isolamento obrigatorio de sessao CLI por chat

Antes de qualquer operacao em terminal/CLI, leia e cumpra a secao `Isolamento obrigatorio de sessao CLI por chat` de `AI-TO-CLI-PROTOCOL.md`. Cada chat deve usar sessao/namespace CLI exclusivo; reutilizacao de sessao entre chats e proibida. Estado necessario para retomada deve ser persistido fora da memoria do shell.
Regra de continuidade: leia e cumpra `AI-TO-CLI-PROTOCOL.md`, especialmente `Continuidade obrigatoria diante de falha de ferramenta ou comando`; erro de ferramenta nao autoriza encerrar a tarefa.

## Continuidade obrigatoria
Todo agente deve cumprir o `PROTOCOLO OBRIGATORIO DE CONCLUSAO DE TAREFAS` em `AI-TO-CLI-PROTOCOL.md`; erro de ferramenta ou resultado parcial nunca e motivo para parar.

<!-- EXECUTION_PROVENANCE_POLICY_V1 -->
## Assinatura e origem obrigatorias de toda execucao

Antes de qualquer acao material, leia e cumpra EXECUTION-PROVENANCE-POLICY.md. Toda execucao automatizada ou operacional deve carregar identidade, origem e execution_id verificaveis; recursos temporarios devem ter owner/origin e cleanup. Use scripts/emit-execution-provenance.py como formato de referencia. Nunca registre secrets.


<!-- BROWSER_SESSION_POLICY_V1 -->
## Navegador: escolha de host e cleanup obrigatorio
Antes de browser interativo/remoto, se o host nao estiver explicitamente definido na tarefa, pergunte qual maquina usar. Sessoes invisiveis/headless transitorias devem ter ownership + TTL padrao de 2h renovavel por heartbeat e cleanup ao final/boot. Orfaos podem ser limpos antes; sessoes visiveis e bridges persistentes documentadas devem ser preservadas. Nunca matar navegador globalmente por nome de processo. Leia a politica completa em `REGRAS-AGENTES-CENTRALIZADAS.md` (BROWSER_SESSION_POLICY_V1).
