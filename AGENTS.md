<!-- CORRIGIR_CADA_ERRO_ABSOLUTO_V1 -->
## REGRA ABSOLUTA DO PROPRIETARIO — corrigir cada erro encontrado

**Aplica-se a TODOS os agentes, auditorias, revisores, controladores e tarefas, inclusive erros preexistentes, intermitentes, secundários, de CI, API, UI, infraestrutura e novos erros encontrados durante o proprio reparo.** Nenhum achado verdadeiro pode ser ignorado, silenciado, classificado artificialmente como verde ou quitado apenas por relatorio, issue, PR, CI, merge ou delegacao.

Para cada falha: **registrar evidencia e responsavel -> reproduzir RED quando viavel -> investigar causa raiz -> corrigir com seguranca e autorizacao -> testar GREEN e regressao -> buscar falhas equivalentes -> prevenir recorrencia -> validar no runtime/UI real E2E e reauditar**. Corrigir achados seguros/autorizados imediatamente; erros fora do escopo imediato exigem encaminhamento rastreavel ao responsavel sem omissao. Novo erro reabre o ciclo.

**Gate terminal:** `APTO` e `CONCLUIDO` proibidos enquanto qualquer erro conhecido relevante ao escopo nao tiver correcao comprovada, mesmo com PR/CI verde. Manter checkpoint `RUNNING/NAO_APTO` com `next_action` e evidencias. Modo SOMENTE LEITURA nao pode mutar: registrar e encaminhar a executor autorizado. `BLOCKED_EXTERNAL` exige prova de impedimento externo, alternativas seguras esgotadas, responsavel e condicao exata de desbloqueio; nunca e APTO. **Nao contornar MFA, RBAC, branch protection, seguranca da plataforma, locks/leases/fencing, secrets, consentimento ou aprovacoes destrutivas.** A politica completa e canônica para todos os repositorios ShopVivaliz esta em `Vivaliz-site/site-shopvivaliz/AGENTS.md` (`CORRIGIR_CADA_ERRO_ABSOLUTO_V1`), em reforco a `DIAGNOSTIC_REMEDIATE_VALIDATE_GLOBAL_V1`.
<!-- /CORRIGIR_CADA_ERRO_ABSOLUTO_V1 -->

<!-- AUDIT_UI_EVIDENCE_INTEGRITY_V2 -->
## Auditoria Extrema V5: UI grafica real, evidencias e continuidade

Se o sistema possuir UI, executar todas as jornadas operacionais diretamente na UI grafica sob conta autorizada; seguir `docs/quality/AUDIT_UI_EVIDENCE_INTEGRITY_V2.md` para inventario, evidencias fisicas com SHA real, acoes/controles/casos, reauditoria independente, RED/GREEN/regressao e pos-deploy. Mecanismo de emails e workers sem UI deve provar essa ausencia no inventario e usar E2E do provider real. Nao declarar APTO por testes isolados, APIs ou flags. Manter `RUNNING` com `next_action` duravel ate certifier oficial devolver `AUDIT_VERDICT=APTO`; `BLOCKED_EXTERNAL` nao e sucesso. Nao violar sender_blocked.pause, MFA, privacidade, permissoes nem custos.
<!-- /AUDIT_UI_EVIDENCE_INTEGRITY_V2 -->

<!-- EXTREME_AUDIT_UI_FIRST_HARD_GATE_V1 -->
## GATE INEGOCIAVEL: Auditoria Extrema V5 executada pela UI real

**Ordem explicita do proprietario (2026-10-13), vinculante a GPT, Claude, Gemini, Codex, subagentes, orquestradores e revisores:** toda auditoria extrema/completa/V5/aptidao de sistema que tenha UI **DEVE ser executada pelo proprio agente atraves da interface grafica real**. O auditor nao pode substituir a UI por API, terminal, SQL, inspecao de codigo, logs, mocks, healthcheck, testes unitarios, Playwright exclusivamente headless nem screenshot estatico. Esses meios sao auxiliares para investigar/reconciliar, jamais prova suficiente do funcionamento que o usuario vivencia.

1. **UI primeiro, sem atalhos:** inventariar telas, jornadas, perfis, estados e casos reais; abrir a interface publicada no host/perfil autorizado; navegar, clicar, preencher, filtrar, salvar/submeter dentro das permissoes; observar resposta visual, erros e efeitos; recarregar, sair e voltar para provar persistencia. Para Amazon Seller Central, Mercado Livre e paineis externos, auditar os casos e transicoes acessiveis na UI oficial, um a um conforme escopo, sem declarar sucesso por API somente.
2. **Evidencia obrigatoria por jornada:** registrar ambiente/URL, SHA/release quando aplicavel, sessao autorizada sem segredos, timestamp, passos efetivamente executados, capturas/trace/video, estado antes/depois, erros de console/rede, reload/revisita e reconciliacao independente dos efeitos duraveis. Screenshot isolado, abertura de pagina, resposta HTTP 200 ou teste simulado nao certificam jornada.
3. **Auditoria inclui reparo:** ao encontrar falha corrigivel no escopo autorizado, investigar causa raiz, corrigir, prevenir recorrencia, executar testes e **repetir o mesmo fluxo pela UI real apos correcao/deploy**, com evidencia independente. Nao encerrar no diagnostico, em PR ou em teste apenas de backend.
4. **Gate fail-closed, sem falso APTO:** qualquer fluxo com UI nao percorrido e comprovado permanece `NAO_VALIDADO_UI` / `NAO_APTO`; e proibido declarar `APTO`, `CONCLUIDO`, 100% ou verde. `browser.required=false` ou `journey.ui=false` nao podem ser usados para ocultar UI existente. Se realmente nao existir interface para o componente auditado, registrar inventario negativo de UI, justificativa e evidencias; validar os caminhos reais nao visuais pertinentes. Ausencia/falha transitoria de browser exige reparo/fallback autorizado antes de `BLOCKED_EXTERNAL`.
5. **Seguranca:** usar browser/desktop/MCP/RDC nos hosts e perfis previstos nos runbooks, com ownership/leases, controles de autorizacao e MFA; preservar sessoes. A auditoria nao autoriza exclusao, faturamento real, modificacao irreversivel ou acesso a segredo. Quando a acao terminal nao puder ser realizada com seguranca, testar ate o limite seguro e registrar exatamente a cobertura pendente; nunca inventar sucesso.

Fonte complementar: `AUDIT_POLICY.md`, `docs/quality/AUDIT_BROWSER_E2E_REAL_V1.md` e `docs/quality/AUDIT_ABSOLUTE_GATE_V1.md` do repositorio governado. **Este gate prevalece sobre instrucoes mais brandas que permitam certificar por API ou parecer do agente.**
<!-- /EXTREME_AUDIT_UI_FIRST_HARD_GATE_V1 -->

<!-- RESUME_EXECUTION_GATE_V1 -->
## Retome / Continue / Prossiga / Siga: execucao obrigatoria ate verificacao

Toda ordem Retome, Continue, Prossiga ou Siga e uma tarefa operacional de execucao, nao pedido de plano, status ou confirmacao generica. O agente principal, Claude, Gemini, Copilot e qualquer subagente devem ler as regras atuais do AGENTS.md no main e registrar prova nao secreta rules_loaded (fonte, ref, SHA, data) antes de mutacoes. Recuperar task_id, ultimo checkpoint e next_action com origem real; nao criar identidades de conversa ou sessoes ficticias.
Executar a proxima acao permitida; investigar erro, corrigir a causa, testar, fazer merge/deploy quando autorizado e validar o objetivo original no runtime. Persistir RUNNING com next_action real enquanto houver caminho seguro viavel; erro de ferramenta, timeout, status Pensando, PR ou ACK nao autorizam encerrar. CONCLUIDO exige evidencia fresca ponta a ponta; BLOCKED_EXTERNAL exige impedimento externo objetivo, alternativas seguras esgotadas e condicao exata de retomada. Quando disponivel, comprovar terminalidade com agent_task_state.py terminal --task <task_id>.
Nao contornar MFA, RBAC, aprovacao sensivel, branch protection ou direitos de outra sessao. Evitar mensagens intermediarias desnecessarias quando o proprietario pedir para nao postar; se limite externo interromper a execucao, salvar checkpoint verdadeiro e nao prometer trabalho de fundo sem mecanismo realmente ativo. Encaminhar as mesmas obrigacoes ao agente delegado.
<!-- /RESUME_EXECUTION_GATE_V1 -->

<!-- REMOTE_ACCESS_EXHAUSTION_GATE_V1 -->
## Gate obrigatório: esgotar acesso remoto antes de declarar bloqueio
Em `Retome`, `Continue`, `Prossiga`, `Siga` ou qualquer tarefa remota, uma falha de MCP/RDC/SSH/rede/autenticacao isolada **não** encerra a execução. Ler AGENTS.md, runbooks locais e `Vivaliz-site/site-shopvivaliz/docs/knowledge/host-access.md` (main atual), comprovando fonte e revisao. Identificar host, identidade e permissoes efetivas.
**Verificar todas as rotas aplicaveis, existentes e autorizadas, na prioridade do runbook:** ShopVivaliz Remote Control MCP/controller; RDC e RDC 2 se disponiveis/autorizados; SSH privado/VCN/Tailscale/tunel/reverse SSH documentado; `desktop_*`/bridge/RustDesk para GUI; OCI Bastion, OCI Compute Run Command, serial console e GitHub Actions somente para bootstrap/recovery/reparo, nunca como transporte normal de runtime. Browser ShopVivaliz permanece na VM backend, sem migracao para Windows. Para cada rota, testar conectividade, identidade e capacidade real; corrigir falhas tecnicas autorizadas, recuperar servico/sessao e aplicar retry idempotente e limitado ou fallback.
Registrar checkpoint nao secreto `remote_access_attempts` por host: rota, objetivo, `PASS/FAILED/NOT_PROVISIONED/NOT_APPLICABLE`, evidencias, causa, reparos e alternativa seguinte. Nao apresentar rota nao provisionada como testada. Manter `RUNNING` enquanto houver acesso alternativo viavel. **`BLOCKED_EXTERNAL` apenas apos exaurir e documentar todos os caminhos tecnicamente viaveis, seguros e autorizados.** `AWAITING_APPROVAL` exige identificar aprovacao obrigatoria exata. Proibidos bypass de MFA/RBAC/branch protection, exibir credenciais, abrir SSH publico, alterar browser para Windows sem autorizacao expressa ou loops infinitos.
<!-- /REMOTE_ACCESS_EXHAUSTION_GATE_V1 -->

<!-- GLOBAL_RESUME_VERIFIED_RULES_V3 -->
## Retome obrigatorio: leitura comprovada e execucao ate validacao
- `Retome`, `Continue`, `Prossiga` e `Siga` isolados sao ordens de executar a ultima tarefa pendente, nunca somente relatar status.
- Antes de cada retomada ou mutacao, ler o AGENTS.md vigente e a base canonica em Vivaliz-site/site-shopvivaliz: docs/knowledge/atendimento-chatgpt-bootstrap.md, host-access.md, README.md, agent-rules.md e runbooks especificos. Registrar checkpoint nao secreto `rules_loaded` com paths, refs, SHAs e instante; citar sem ler nao vale. Se sem acesso, recuperar leitura antes de mutacoes.
- Recuperar ultimo checkpoint e executar: identificar causa raiz, corrigir, testar, prevenir, usar fallback autorizado, continuar, validar runtime/E2E, integrar PR e deploy quando aplicavel.
- Proibido encerrar por diagnostico, relatorio, timeout, erro transitorio, CI ou PR. Antes de declarar bloqueio, esgotar e documentar todas as alternativas razoaveis, seguras e autorizadas, sem loops infinitos nem bypass de MFA, CI, aprovacoes ou seguranca.
- Manter RUNNING enquanto houver acao segura viavel; CONCLUIDO apenas com evidencias; BLOCKED_EXTERNAL somente com impedimento externo comprovado e checkpoint recuperavel. Nao prometer persistencia sem controlador ativo.
<!-- /GLOBAL_RESUME_VERIFIED_RULES_V3 -->

<!-- AUTONOMOUS_RESUME_TO_VALIDATED_COMPLETION_V1 -->
## Regra obrigatoria: retomar e executar ate conclusao comprovada

- Em toda tarefa operacional, recuperar o ultimo estado e checkpoint confiavel antes de agir; nao repetir operacoes ja concluidas nem descartar trabalho existente.
- Agir autonomamente dentro das permissoes vigentes. Diagnostico, relatorio, PR aberto, tentativa de comando, timeout ou falha transitoria nao encerram a tarefa.
- Ciclo obrigatorio: **verificar estado -> executar -> identificar falhas -> investigar causa raiz -> corrigir -> prevenir recorrencia -> testar -> retomar -> validar**.
- Diante de erro de browser, MCP, RDC, API, CLI, rede, sessao, worker ou integracao, verificar se a acao anterior teve efeito, recuperar de forma idempotente e tentar alternativas tecnicamente viaveis, seguras e autorizadas.
- Usar checkpoints, logs e estado persistente quando existirem. Nunca alegar trabalho em segundo plano ou retomada automatica se nao houver controlador realmente configurado e ativo.
- Manter a tarefa `RUNNING` enquanto existir proxima acao segura e viavel no ambiente de execucao. Declarar `CONCLUIDO` apenas com evidencias frescas, testes pertinentes, regressao e validacao runtime/E2E quando aplicavel.
- Se houver bloqueio externo objetivo ou aprovacao obrigatoria pendente, registrar causa, evidencias, tentativas, checkpoint e acao exata para retomar; nao contornar protecoes de branch, autenticacao, MFA, politicas de seguranca ou controles de aprovacao.
- Respeitar regras especificas do repositorio, limites da sessao e escopo de autorizacao. Acao destrutiva ou irreversivel exige autorizacao adequada.
- A regra vale para agentes, subagentes, Codex, MCP/RDC, automacoes, debugging, auditorias, deploys e retomadas; a resposta final deve distinguir entrega comprovada de bloqueio documentado.

Fonte global da politica: `Vivaliz-site/site-shopvivaliz/REGRAS-AGENTES-CENTRALIZADAS.md`.
<!-- /AUTONOMOUS_RESUME_TO_VALIDATED_COMPLETION_V1 -->

<!-- AUDIT_EXTERNAL_REMEDIATION_V1 -->
> **AUDITORIA EXTERNA TAMBÉM É CORRETIVA:** auditoria interna, externa, independente, contraditória ou feita por outro agente/revisor segue o mesmo ciclo. Auditor externo com autorização deve corrigir, testar e reauditar. Se for read-only, o relatório não encerra: os achados corrigíveis seguem para executor autorizado e permanecem em andamento até correção + revalidação independente ou bloqueio externo comprovado.
<!-- /AUDIT_EXTERNAL_REMEDIATION_V1 -->

<!-- AUDIT_REMEDIATE_VALIDATE_GLOBAL_V1 -->
## Auditoria corretiva obrigatória

- Todo pedido de auditoria significa **investigar, corrigir, prevenir e validar**; não encerrar apenas relacionando erros.
- Todo achado material corrigível e autorizado deve ter causa raiz investigada, correção aplicada, prevenção pertinente, teste e reauditoria.
- Relatório, recomendação, plano ou issue são estados intermediários enquanto existir ação segura executável.
- APTO/COMPROVADO/CONCLUIDO exigem evidência fresca pós-correção e E2E real quando aplicável; sem falso-verde.
- Pendência só é aceitável após esgotar alternativas seguras, com evidência, causa e ação exata necessária para continuidade.
- Fonte global: `REGRAS-AGENTES-CENTRALIZADAS.md`, policy `AUDIT_REMEDIATE_VALIDATE_GLOBAL_V1`.
<!-- /AUDIT_REMEDIATE_VALIDATE_GLOBAL_V1 -->

<!-- DIAGNOSTIC_REMEDIATE_VALIDATE_GLOBAL_V1 -->
> **DIAGNÓSTICO É CORRETIVO EM QUALQUER TAREFA:** defeito confirmado exige correção segura, prevenção pertinente, testes e validação real/E2E aplicável antes de `CONCLUIDO`. Enquanto houver ação segura executável, permanecer `RUNNING`; somente `BLOCKED_EXTERNAL` comprovado permite encerrar sem corrigir.
<!-- /DIAGNOSTIC_REMEDIATE_VALIDATE_GLOBAL_V1 -->
<!-- GEPETO_EVERY_TASK_V1 -->
## Gepeto obrigatorio em toda tarefa
Acione o plugin Gepeto junto com Superpowers em toda tarefa e retomada, sem nova mencao do usuario. Leia e cumpra `GEPETO-POLICY.md`. Se o runtime nao expuser o plugin, registre `GEPETO_UNAVAILABLE`, informe a limitacao e continue o trabalho autorizado sem simular participacao. Aplicar um plugin nao comprova delegacao nem revisao independente.
<!-- /GEPETO_EVERY_TASK_V1 -->


<!-- SHOPVIVALIZ_REMOTE_ACCESS_V1 -->
## Acesso remoto obrigatório para agentes

Antes de qualquer operação em VM, runtime, navegador, serviço, deploy, logs ou recuperação, leia **`docs/AGENT-REMOTE-ACCESS.md`**. O padrão vigente é SSH privado/Tailscale com `shopvivaliz-agent` para shell, RustDesk self-hosted para GUI, OCI Bastion/control plane auditável quando o ambiente não possui rota privada, e Desktop Commander somente como contingência. Navegador ShopVivaliz deve rodar na VM backend, nunca nos hosts Windows.

# Regras obrigatorias para agentes

<!-- GLOBAL_BROWSER_VM_POLICY_V2 -->
> **NAVEGAÇÃO GLOBAL — VM OBRIGATÓRIA; WINDOWS PROIBIDO PARA BROWSER:** qualquer navegador, automação browser, sessão gráfica, Playwright/Selenium/CDP, Chrome/Chromium/Edge/Opera, CAPTCHA, MFA, consentimento ou validação visual deve usar por padrão e obrigatoriamente a VM backend `always-free-arm-1787907847-26` (`10.0.1.38`) e o Browser Worker privado. Para intervenção humana, usar `https://shopvivaliz.com.br/admin/browser-worker.php`. **Fred-Win (`LAPTOP-NIG4IFUU`) e `DESKTOP-KOCEPSV` não são destinos nem fallback para navegação.** Não perguntar qual máquina usar para browser: use a VM. Exceção somente se o proprietário ordenar explicitamente, na tarefa atual, o uso de um Windows específico para aquela navegação. Se a VM estiver indisponível, reparar o caminho VM/OCI Bastion/túnel privado ou registrar bloqueio real; nunca migrar silenciosamente para Windows. Workflows/relays Windows de browser são legado e não devem ser executados até serem migrados. A regra não proíbe Windows para tarefas não-browser que realmente dependam dele.

<!-- GLOBAL_BROWSER_SESSION_PROFILE_V1 -->
> **SESSAO CANONICA OPENAI/CHATGPT NA VM:** para qualquer navegacao em ChatGPT/OpenAI no Browser Worker, reutilize o contexto persistente existente com `persistent=true` e `profile=ai-squad-chatgpt`. Esse e o perfil canonico que deve preservar a autenticacao ja realizada. Nao criar perfil novo, nao usar `manual` como fallback e nao migrar para Fred-Win/KOCEPSV. Se a autenticacao expirar ou exigir MFA/CAPTCHA, abra **esse mesmo perfil** pela interface autenticada `https://shopvivaliz.com.br/admin/browser-worker.php`, conclua a autenticacao nele e continue reutilizando `ai-squad-chatgpt`. Labels/TTL de sessoes de trabalho podem variar, mas o profile para ChatGPT/OpenAI deve permanecer `ai-squad-chatgpt`, salvo ordem explicita do proprietario na tarefa atual.

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


<!-- AUDIT_ABSOLUTE_V5_ENTRYPOINT -->
## Auditoria Extrema V5 absoluta — entrada obrigatória
Antes de qualquer auditoria completa/extrema, validação de release ou declaração de aptidão, leia e execute integralmente `AUDIT_POLICY.md`, `docs/quality/AUDIT_ABSOLUTE_GATE_V1.md`, `docs/quality/AUDIT_BROWSER_E2E_REAL_V1.md`, `docs/quality/AUDIT_APTO_REMEDIATION_LOOP_V1.md`, `docs/quality/AUDIT_AUTH_CREDENTIAL_DISCOVERY_V1.md`, `docs/quality/AUDIT_PROJECT_REQUIREMENTS_V1.md` e `docs/quality/AUDIT_PROJECT_REQUIREMENTS.json`.
Se existir UI, o próprio agente executa E2E real no navegador gráfico no mesmo release. API/CLI/headless-only não certificam. Todo bloqueador executável deve ser corrigido, testado, deployado quando aplicável e reauditado até o certifier retornar `AUDIT_VERDICT=APTO`. Antes de declarar bloqueio por login/credencial, esgote a descoberta segura em todos os repositórios governados e fontes canônicas sem expor secrets.


<!-- AUDIT_MERGE_ENFORCEMENT_V1 -->
## Enforcement absoluto de merge/main
Para auditoria/aptidão, cumpra `docs/quality/AUDIT_MERGE_ENFORCEMENT_V1.md`. O gate local deve executar `scripts/absolute-audit-governance-validate.sh`, e todo push em `main`/`master` deve passar pelo **Absolute Audit Main Guard** com prova de PR mesclado.

<!-- GLOBAL_TASK_CONTINUITY_V8 -->
## Global task continuity V8
Toda tarefa que possa alterar código, infraestrutura, dados, CI ou deploy deve manter checkpoint durável via `python3 scripts/agent_task_state.py`. Este repositório é fixado como `repository=fredmourao-ai/mei-mg-email`. Falhas recuperáveis permanecem RUNNING e conclusão exige verificação fresca. O adapter falha fechado sem o controlador canônico injetado pelo runtime detached. Background recovery permanece Gemini-only; Codex nunca é fallback automático e continua sendo a última opção finita explícita.
<!-- /GLOBAL_TASK_CONTINUITY_V8 -->

<!-- CHECKPOINT_FIRST_V9 -->
## Checkpoint antes da primeira etapa material
Toda tarefa potencialmente longa ou mutável deve registrar `agent_task_state.py start`
**antes** da primeira investigação extensa, chamada remota material, edição, mutação,
execução longa, delegação ou espera de CI. O objetivo é eliminar a janela em que uma
interrupção do ChatGPT ocorre antes de existir estado durável.

Depois de cada avanço material, atualize `progress` com evidência e `next_action`.
Não adie o primeiro checkpoint para depois do diagnóstico. Se o contexto atual não
consegue alcançar o controlador canônico, falhe fechado para tarefas que dependem de
retomada automática e use a rota operacional auditável que consiga registrar o estado.
<!-- /CHECKPOINT_FIRST_V9 -->

<!-- SHOPVIVALIZ_GRAPHICAL_SESSION_RECOVERY_V1 -->
## Gate obrigatorio para todos os agentes: GUI ShopVivaliz e contas ChatGPT

Antes de diagnosticar RustDesk, VM, autenticacao Dev/Atendimento ou classificar um login como perdido, **ler efetivamente no `main` de `Vivaliz-site/site-shopvivaliz`** o runbook `docs/knowledge/shopvivaliz-graphical-session-recovery.md`, junto de `AGENTS.md` e `docs/knowledge/browser-sessions.md`, registrando `rules_loaded` com SHAs. Esta regra aplica-se a ChatGPT, Claude, Gemini, Gepeto, subagentes e rotinas persistentes deste repositorio.

Fatos observados em 2026-10-11: a area XFCE/RustDesk `fredconsole/:0` foi recuperada e mostrou Chromium ChatGPT no workspace Vivaliz com Dev e Atendimento no seletor; a tela LightDM `lightdm/:1` e login do **Ubuntu**, nao login ChatGPT; os perfis corporativos independentes permanecem no usuario `fredrdp`, display `:99`, Dev CDP9559 e Atendimento CDP9556. **Ver conta no seletor nao prova autenticacao individual**: exigir identidade exata em `/api/auth/session` no respectivo perfil antes de marcar `AUTHENTICATED`/`CONCLUIDO`. Nao reutilizar cookies entre perfis, nao destruir sessoes, nao solicitar senha ja provisionada e nao redefinir o GNOME Keyring por tentativa. Usar somente senha existente + TOTP oficial conforme preferencia atual do proprietario, respeitando etapas do provedor, MFA, lease e aprovacoes. Preservar checkpointer e monitor; `RUNNING` ate progresso real.
<!-- /SHOPVIVALIZ_GRAPHICAL_SESSION_RECOVERY_V1 -->
