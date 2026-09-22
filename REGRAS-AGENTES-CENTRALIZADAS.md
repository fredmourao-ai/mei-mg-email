# 📋 REGRAS PARA AGENTES IA - FONTE ÚNICA CENTRALIZADA

**Efetivo:** 2026-07-24
**Escopo:** Todos os agentes (Claude, Codex, Gemini, GPT, etc.)
**Aplicável a:** Qualquer tarefa automatizada (deploy, testes, integrações, ERP, pagamentos, emails, secrets)
**Objetivo:** Eliminar falsos positivos, exigir evidência verificável antes de declarar sucesso

> ⚠️ **ESTA É A FONTE ÚNICA DE VERDADE PARA TODAS AS REGRAS.**
> Outros arquivos (VALIDATION-POLICY.md, SECRETS-SYNC-RULE.md, etc.) são DEPRECADOS.
> Veja [Referências Cruzadas](#referências-cruzadas) para documentação específica.

---

<!-- SUPERPOWERS_EVERY_STAGE_V1 -->
## 🧭 @Superpowers obrigatório em cada etapa de toda conversa/agente (2026-09-19)

Esta regra é vinculante para **todos os agentes, chats, conversas, sessões e retomadas que operem projetos ShopVivaliz** (Claude, Codex, Gemini, GPT e demais agentes).

- Toda tarefa deve iniciar sob **@Superpowers** e permanecer sob essa metodologia até a conclusão validada.
- **Não basta invocar ou mencionar @Superpowers uma única vez.** Ao entrar em cada etapa material, o agente deve reaplicar o workflow/skill de Superpowers adequado à fase.
- As etapas materiais incluem, no mínimo: bootstrap/contexto, planejamento, investigação, coleta de evidências, implementação, debugging sistemático, TDD/testes, revisão, correções, PR/checks/merge, deploy, validação pós-deploy, auditoria caso a caso e encerramento.
- Comandos de continuidade como **“retome”, “continue”, “prossiga” ou equivalentes** devem recuperar o último checkpoint comprovado e continuar com @Superpowers; não recomeçar do zero nem abandonar a metodologia.
- Em transições de fase, selecionar explicitamente a disciplina Superpowers aplicável (por exemplo planejamento, TDD, debugging, revisão/validação) antes de executar a próxima ação.
- Se o runtime atual não expuser a capacidade @Superpowers, **não fingir que ela foi chamada**: registrar `SUPERPOWERS_UNAVAILABLE`, aplicar manualmente a mesma disciplina de planejamento/TDD/debugging/verificação e continuar até encontrar um runtime que a exponha, quando isso for necessário.
- A resposta final só pode ser emitida depois que as etapas aplicáveis tiverem sido executadas e validadas com evidência independente.

Esta regra é contínua e prevalece sobre hábitos de sessão que tratem Superpowers apenas como bootstrap inicial.

## ✅ AUTORIZAÇÃO OPERACIONAL DO PROPRIETÁRIO (2026-08-01)

O proprietário autoriza os agentes que tenham capacidade técnica e acesso válido a:

- validar a entrega de ponta a ponta em navegador real, incluindo interação, persistência e evidência visual;
- deixar a mudança pronta para revisão com resumo, riscos e evidências verificáveis;
- aprovar pull requests, fazer merge e acionar ou executar o deploy sem aguardar uma nova aprovação explícita do proprietário, desde que os checks, as proteções e os critérios do repositório permitam a ação;
- acompanhar o gate e a produção até obter evidência do resultado.

Fluxo padrão: depois de validar a entrega e deixá-la pronta para revisão, o agente conclui a aprovação/merge autorizado e acompanha o Quality Gate, o deploy automático e o smoke test até o resultado final. Não deve interromper o fluxo para pedir confirmação intermediária.

Esta autorização remove apenas a espera por uma aprovação adicional. Ela não autoriza force-push, bypass de branch protection, exposição de secrets, cobrança real, exclusão destrutiva de dados ou declaração de sucesso sem evidência. Antes de merge/deploy, o agente deve confirmar o SHA alvo, os checks do PR, a validação real aplicável e, quando houver alteração publicada, a release ativa, os logs e o smoke test de produção. Se a plataforma bloquear autoaprovação ou outra etapa, o agente não deve contornar a proteção: deve registrar o bloqueio como **INCONCLUSIVO**.

## 🛡️ SEGURANÇA DE AUTOMAÇÃO DE UI E AÇÕES DESTRUTIVAS (2026-09-01)

Autonomia, conclusão ponta a ponta e autorização operacional **não ampliam o escopo destrutivo**. Exclusão, remoção, reset, revogação ou outra ação irreversível só é permitida quando **o alvo e o resultado destrutivo exatos** estiverem no pedido atual do proprietário. Pedidos genéricos como investigar, auditar, limpar, corrigir, concluir tudo ou fazer o necessário não autorizam apagar projetos, chats, contas ou dados por inferência.

- **Probe, diagnóstico, auditoria, health check e observação são somente leitura.** É proibido invocar `Excluir`, `Delete`, `Remove`, `Reset`, `Revogar` ou confirmação destrutiva em dados reais durante esse tipo de tarefa.
- Se for indispensável testar exclusão, use fixture/sandbox criada especificamente para o teste; nunca um projeto, chat, conta ou dado real do proprietário.
- É proibido criar task agendada, serviço, script oculto ou processo elevado para contornar limites de permissão de ferramenta ou executar automação destrutiva de UI.
- Tasks temporárias de UI não podem permanecer ativas após a tarefa e não devem usar `RunLevel Highest` como ponte para interação com aplicações do usuário.
- Nomes devem descrever o efeito real. Um payload que altera estado nunca pode ser rotulado como `probe`, `check`, `audit` ou equivalente somente-leitura.
- Antes de atribuir uma execução a terceiro, o agente deve correlacionar timestamps com **suas próprias chamadas de ferramenta e logs**. É proibido reportar como atividade externa uma ação que o próprio agente disparou.
- `LastResult=0`, exit code 0 ou ausência de exceção comprovam apenas término técnico; não comprovam o efeito de negócio nem justificam inferir que uma exclusão foi concluída.
- Em incidente, preserve evidência e hashes antes de limpar artefatos. O material preservado deve ficar fora de caminhos de execução automática.

Estas regras prevalecem sobre qualquer protocolo de autonomia, insistência até conclusão ou orientação para não pedir confirmação.

---
### Commit, PR e Merge obrigatório ao finalizar rodada de alterações

> ⚠️ **REGRA DE FINALIZAÇÃO OBRIGATÓRIA — COMMIT NÃO FINALIZA TAREFA:**
> O único fluxo de conclusão aceito para alteração versionada é **branch → validação real → commit → push → PR → checks/revisão → merge → validação pós-merge → working tree limpa → zero PR pendente da própria rodada**.
>
> Um commit local, um push de branch, uma PR aberta/draft ou uma PR verde ainda sem merge são apenas estados intermediários. O agente deve continuar autonomamente enquanto houver ações executáveis necessárias para chegar ao merge e à validação final.
>
> Antes de declarar `COMPROVADO`, o agente deve verificar `git status --porcelain` vazio no workspace da tarefa e consultar as PRs relacionadas para confirmar que nenhuma ficou aberta/draft. Após merge, deve verificar o ramo/deploy alvo e registrar a evidência pós-merge.
>
> Se um bloqueio externo real impedir o merge depois de esgotadas as correções disponíveis, o resultado é **INCONCLUSIVO**. Não é permitido abandonar PR aberta como estacionamento: PR obsoleta, duplicada ou sem caminho executável para merge deve ser fechada/limpa com o motivo e ponto exato de continuação documentados.

Ao concluir qualquer rodada de alterações versionadas, o agente deve deixar a mudança integrada por merge no ramo alvo e/ou publicada no alvo de deploy autorizado, desde que checks, revisões e proteções permitam. Não é aceitável encerrar uma rodada como "pronta" mantendo apenas branch local ou remoto sem merge/deploy quando o agente tem acesso técnico para concluir o fluxo. Se branch protection, CI, falta de permissão ou outro gate impedir o merge, o resultado deve ser registrado como **INCONCLUSIVO**, com link/SHA, checks observados e próximo bloqueio concreto.

Simulação não substitui execução real: testes secos, mocks, screenshots headless, `curl` isolado ou inspeção de código são apenas preparação. Para declarar entrega, o agente deve executar a rotina real aplicável e validar o efeito por evidência independente, incluindo navegador real para UI, sem gerar cobrança real, alterar preço/estoque/pedido fora do escopo, expor secrets ou contornar proteções.

---

## 💸 POLÍTICA OBRIGATÓRIA DE CONSUMO DE IA E EXECUÇÃO RECORRENTE (2026-09-01)

Esta política é vinculante para **todos os projetos, hosts, workflows, serviços, timers, cron jobs, Scheduled Tasks, scripts, agentes e rotinas autônomas**.

1. **Rotina permanente, periódica, agendada, daemon, watcher ou loop não pode usar Claude, GPT/OpenAI, Codex ou qualquer outro modelo pago por padrão.** Se IA for realmente necessária nesse tipo de rotina, deve usar primeiro uma opção gratuita/local explicitamente aprovada (por exemplo Ollama/local ou cota gratuita comprovada), com fallback determinístico sem IA. É proibido fazer fallback silencioso de IA gratuita para provedor pago.
2. **Claude/GPT/Codex pagos são permitidos somente para tarefas finitas, iniciadas para atingir um objetivo concreto e que terminem ao concluir ou bloquear de forma real.** Eles não podem permanecer como daemon, supervisor, polling loop, autorepair, watchdog ou consumidor recorrente.
3. **Toda execução finita de IA paga deve ter circuit breaker.** Definir limites coerentes de duração, tentativas/retries, chamadas ao modelo e tamanho de trabalho/contexto. `while true`, retry ilimitado, relançamento automático e continuidade sem teto são proibidos para consumidores pagos. Se o limite for atingido, persistir checkpoint e encerrar; uma nova execução só pode ocorrer por novo evento/tarefa explícita, nunca por loop de consumo.
4. **Antes de habilitar ou manter uma automação, auditar cada consumidor individualmente.** Registrar: arquivo/comando, host, gatilho, frequência, provedor/modelo, se há custo, timeout, retries, limite de chamadas, condição de saída, necessidade real do processo e evidência de que não existe duplicação/órfão. Não assumir que um processo é necessário apenas porque já está instalado ou ativo.
5. **Serviço contínuo só é legítimo quando a natureza do serviço exige continuidade.** Monitoramento, fila, API, renovação de token e health-check devem ser preferencialmente determinísticos. Trabalho periódico finito deve usar timer/cron + `oneshot`, e não processo infinito com `sleep`, quando não houver necessidade de daemon.
6. **Processo travado, órfão ou sem progresso deve ser encerrado e investigado, não reiniciado indefinidamente.** Supervisores devem diferenciar falha transitória de erro persistente e possuir backoff, máximo de reinícios em janela e estado de bloqueio/cooldown.
7. **Eventos de GitHub não podem disparar IA paga de forma ampla.** Workflows com Claude/GPT/Codex devem exigir gatilho explícito e restrito (por exemplo comando/label/dispatch autorizado), ter `timeout-minutes`, `concurrency` e cancelamento de execução obsoleta quando aplicável. Comentários, reviews, issues, pushes ou schedules genéricos não podem consumir IA paga automaticamente.
8. **Fallback deve priorizar custo zero:** determinístico → local/gratuito → pago somente em tarefa finita explicitamente autorizada. Para rotinas recorrentes, a cadeia termina antes do provedor pago.
9. **Teste de credencial não deve consumir modelo sem necessidade.** Preferir validação de formato/configuração/endpoint sem geração; quando uma chamada real for indispensável, ela deve ser manual/finita, mínima e sem repetição automática.
10. **Observabilidade obrigatória:** consumidores de IA devem registrar, sem secrets, pelo menos início/fim, motivo/gatilho, provedor/modelo, quantidade de tentativas, duração, resultado e identificador da tarefa. Onde a API expuser uso, registrar métricas de tokens/custo agregadas. Alertar e bloquear comportamento anômalo.

### Critério de classificação obrigatório

| Tipo | Forma correta | IA paga |
|---|---|---|
| API/worker que precisa ficar online | serviço contínuo, lógica determinística | **PROIBIDA em loop** |
| Verificação periódica | timer/cron + job `oneshot` finito | **PROIBIDA** |
| Watchdog/autorepair | regras determinísticas + backoff/cooldown | **PROIBIDA** |
| Resolução complexa sob demanda | tarefa finita com timeout/budget | Permitida, se necessária |
| Revisão/implementação por agente | execução finita até conclusão, com circuit breaker | Permitida |
| Conflito/triagem automatizada | determinístico ou IA local/gratuita | Paga somente por disparo manual explícito |

**Regra de ouro:** concluir a tarefa não significa deixar o agente rodando. O estado final correto de Claude/GPT/Codex é **processo encerrado** após a tarefa; continuidade operacional pertence a software determinístico ou IA gratuita/local com limites.

## AUDITORIA_EXTREMA_UNIVERSAL_V4 — regra obrigatória para todos os agentes

Auditoria extrema não é uma lista fechada de checks. Nos gatilhos definidos em `AUDIT_POLICY.md`, executar o conjunto canônico de `docs/quality/`: protocolo extremo, runtime parity, cobertura universal, self-test quando aplicável e overlay. Procurar erros explícitos e silenciosos, classes conhecidas e unknown unknowns, reconciliar dados/efeitos e corrigir achados SAFE antes de concluir.

A política não promete excluir matematicamente todos os erros possíveis; ela exige cobertura de todas as classes materiais conhecidas, busca adversarial por classes desconhecidas e declaração explícita de qualquer dívida de evidência.

## 🎯 PRINCÍPIOS FUNDAMENTAIS (4 REGRAS INVIOLÁVEIS)

### 1. NUNCA declare sucesso sem evidência INDEPENDENTE

**Proibido:**
```
❌ "O webhook deve ter sido enviado"
❌ "Provavelmente funcionou"
❌ "A máquina parecia responder bem"
❌ "Nenhum erro na saída, então deve estar OK"
```

**Obrigatório:**
```
✅ "Webhook confirmado: POST /webhook HTTP 200 às 14:31:08 UTC, body: {...}"
✅ "Pedido verificado no banco: SELECT * FROM orders WHERE id='ABC' ✓ status='approved'"
✅ "Health check respondeu: GET /health HTTP 200 {'status':'up'}"
```

---

### 2. NUNCA considere ação MANUAL como prova de AUTOMAÇÃO

**Proibido:**
```
❌ Executar git pull manualmente e depois afirmar que daemon sincronizou
❌ Criar o arquivo esperado e depois verificar que apareceu
❌ Reiniciar manualmente um serviço e depois afirmar que se recuperou automaticamente
❌ Chamar uma API manualmente e depois declarar que webhook funcionou
```

**Separação obrigatória:**

| Fase | Ação | Responsável | O que Provar |
|------|------|-------------|-------------|
| **Preparação** | Setup, registrar estado anterior | Agente ou Humano | Estado inicial |
| **Disparo** | Criar mudança que deve desencadear automação | Agente ou Humano | Mudança commitada/enviada |
| **Espera** | ⏸️ NÃO FAÇA NADA | Ninguém | Deixar sistema agir |
| **Observação** | Verificar resultado via método **DIFERENTE** | Agente | Prova de efeito automático |

---

### 3. QUALQUER ERRO INTERROMPE A ROTINA

**Obrigatório em todo script:**

```bash
#!/bin/bash
set -Eeuo pipefail  # ← INVIOLÁVEL

git fetch origin    # ← Se isso falha, próximas linhas não rodam
git merge --ff-only # ← Não roda se git fetch falhou
```

---

### 4. RESULTADO SÓ PODE SER: COMPROVADO, FALHOU ou INCONCLUSIVO

**Não existe "parece funcionar", "provavelmente OK", "acho que".**

| Status | Significado | Evidência Mínima |
|--------|------------|------------------|
| ✅ **COMPROVADO** | Prova independente e verificável | SHA bate, log mostra execução |
| ❌ **FALHOU** | Erro confirmado com código/log | Exit code ≠ 0, mensagem de erro |
| ⚠️ **INCONCLUSIVO** | Não conseguiu verificar | Sem acesso a logs, sem SSH |

---

## 🚩 RED FLAGS - PROIBIÇÕES AUTOMÁTICAS

**Se qualquer destes eventos ocorrer, agente fica PROIBIDO de concluir sucesso:**

### Erros Detectados
- ❌ `error:` em qualquer saída
- ❌ `fatal:` em qualquer saída
- ❌ `rejected:`, `denied:`, `timeout`
- ❌ `FileNotFoundError`, `Permission denied`, exceções

### Códigos de Saída
- ❌ Exit code ≠ 0 (qualquer)
- ❌ Comando retornou silenciosamente

### Padrões Perigosos
- ❌ Continuação após erro (`|| echo "OK"`)
- ❌ Supressão de erros (`2>/dev/null` sem justificativa)
- ❌ Forçar sucesso (`|| true` sem lógica)
- ❌ Intervenção manual durante teste de automação

### Dados Insuficientes
- ❌ Sem logs relevantes
- ❌ Sem timestamps
- ❌ Sem comparação antes/depois
- ❌ Sem validação independente

### Inferência (PROIBIDA)
- ❌ "Deve ter funcionado"
- ❌ "Provavelmente OK"
- ❌ "Nenhum erro visto"

---

## 📊 MATRIZ DE EVIDÊNCIAS POR TIPO DE TAREFA

### Deploy de Código
| Componente | Evidência Mínima |
|-----------|-----------------|
| Git | SHA local = SHA remoto; push confirmado |
| SSH/VM | Conexão bem-sucedida; arquivo verificado |
| HTTP | GET / retorna HTTP 200 com conteúdo esperado |
| Logs | Logs de deploy sem erros |

### Git & Sincronização
| Componente | Evidência Mínima |
|-----------|-----------------|
| Commit | SHA local completo + mensagem |
| Push | git push output confirmando envio |
| Remoto | git ls-remote mostra novo SHA |
| Daemon | Log mostrando git fetch + git merge |
| Confirmação | SHA VM = SHA GitHub (via SSH) |

### Webhook & Callbacks
| Componente | Evidência Mínima |
|-----------|-----------------|
| Envio | HTTP POST confirmado (HTTP 2xx, exit 0) |
| Recepção | Log do servidor mostrando POST recebido |
| Processamento | Webhook handler executado sem erro |
| Persistência | Dados atualizados no banco |
| Validação | Mudança verificada com SELECT ou API |

### API & Integração
| Componente | Evidência Mínima |
|-----------|-----------------|
| Request | HTTP status 2xx |
| Response | JSON/XML com chaves esperadas |
| Idempotência | Mesma request 2x retorna mesmo resultado |
| Persistência | Dado criado + SELECT confirmação |

### Banco de Dados
| Componente | Evidência Mínima |
|-----------|-----------------|
| INSERT | Execute; validar exit 0 |
| Confirmação | SELECT retorna row criado |
| Idempotência | INSERT duplicado trata apropriadamente |

### Pagamento (Mercado Pago, etc.)
| Componente | Evidência Mínima |
|-----------|-----------------|
| Webhook | POST recebido; HTTP 200; log servidor |
| Signature | HMAC-SHA256 validado |
| Order Status | UPDATE confirmado |
| Email | SMTP aceitou; verificar INBOX |
| ERP | GET /orders mostra dados refletidos |

### E-mail
| Componente | Evidência Mínima |
|-----------|-----------------|
| SMTP | Connection accepted; AUTH OK; RCPT OK |
| Envio | SMTP 250 Message accepted |
| Entrega | Verificar INBOX no destino |
| Conteúdo | Subject, to, body corretos |

### ERP & Olist & Shopee
| Componente | Evidência Mínima |
|-----------|-----------------|
| Autenticação | API key aceita; sem key → 401 |
| Sincronização | GET /orders → HTTP 200 |
| Criação | POST → 201 com ID único |
| Confirmação | Dado aparece em ERP via API |
| Idempotência | Sem duplicação com idempotency_key |

### Agente IA (Automação 24/7)
| Componente | Evidência Mínima |
|-----------|-----------------|
| Execução | Log mostrando agente iniciado |
| Ação | Agente executou operação (em log) |
| Efeito | Mudança real observada |
| Validação | Efeito verificado independentemente |
| Erro | Qualquer erro em log; agente não continua |

### Alterações de Interface (UI/UX) / Frontend
| Componente | Evidência Mínima | Responsabilidade |
|-----------|-----------------|------------------|
| Renderização | **SCREENSHOT REAL** no browser (não simulado) | **AGENTE + USUÁRIO** |
| Responsividade | **SCREENSHOT REAL** em Desktop e Mobile | **AGENTE + USUÁRIO** |
| Estilo/Layout | **SCREENSHOT REAL** sem quebras, imagens OK | **AGENTE + USUÁRIO** |
| Interações (JS) | **SCREENSHOT REAL** após interação | **AGENTE + USUÁRIO** |
| CSS/Cor Específica | **SCREENSHOT REAL** mostrando cor correta | **AGENTE + USUÁRIO** |

**⚠️ OBRIGATÓRIO - REGRA INVIOLÁVEL (UI):**

```
NÃO ACEITO validação teórica ou simulada:
  ❌ curl + grep (pode estar em cache, pode não renderizar igual)
  ❌ headless browser screenshots (falta interação real, fonts podem não carregar)
  ❌ "o código está certo, deve funcionar" (inferência, não evidência)

ACEITO APENAS:
  ✅ Screenshot REAL de navegador REAL (Chrome, Firefox, Safari)
  ✅ Navegador com cache limpo (Ctrl+Shift+Delete)
  ✅ Modo normal + modo anônimo (ambos)
  ✅ Desktop + Mobile (se aplicável)
  ✅ Mostrando a mudança de forma inequívoca

PROCESSO OBRIGATÓRIO:
1. Agente pode usar curl/API/testes apenas como preparação e diagnóstico.
2. O PRÓPRIO AGENTE abre o release/ambiente alvo no navegador real da VM canônica.
3. O agente percorre a jornada completa pela UI: navega, clica, preenche, submete e observa estados intermediários.
4. O agente captura evidência visual + console/rede e confirma a pós-condição.
5. O agente recarrega, navega para fora, retorna e confirma persistência.
6. Quando houver efeito durável/externo, reconcilia por canal independente.
7. O usuário NÃO é responsável por completar o E2E do agente. Screenshot humano é apenas evidência complementar.
8. Em Auditoria Extrema, somente o certifier absoluto pode autorizar APTO.
```

**Se Playwright/Selenium não disponível no servidor:** Agente declara INCONCLUSIVO e pede screenshot real.

---

## 🔐 SINCRONIZAÇÃO OBRIGATÓRIA DE SECRETS (3 AMBIENTES)

### Regra Crítica
> **CRÍTICO**: Toda alteração de secret DEVE ser sincronizada em TODOS os 3 ambientes simultaneamente.
> **Nunca** deixar um secret desincronizado por mais de 5 minutos.

### Quando Aplica
**OBRIGATÓRIO sincronizar quando:**
- ✅ Adicionar novo secret
- ✅ Atualizar valor de secret (rotação)
- ✅ Remover secret deprecado
- ✅ Renovar token expirado

**Exemplo de NÃO sincronizar = ERRO:**
```
❌ Atualizar OLIST_REFRESH_TOKEN só em GitHub
❌ Adicionar NOVO_API_KEY só no local
❌ Rotacionar MERCADOPAGO_TOKEN só na VM
```

### Checklist de Sincronização

#### Passo 1: EDITAR
```bash
# Local: C:\Users\FRED\site-shopvivaliz\.env (ou C:\Users\user\...)
vi .env
```

#### Passo 2: COPIAR para VM
```bash
# Dependendo do perfil do Windows ativo (FRED ou user)
SSH_KEY="C:\Users\user\Downloads\ssh-key-2026-07-04.key"  # ou FRED
scp -i "$SSH_KEY" .env ubuntu@137.131.156.17:/home/ubuntu/site-shopvivaliz/.env
```

#### Passo 3: ATUALIZAR GitHub
```bash
# Via GitHub CLI
gh secret set NOME_SECRET --body "valor"

# OU: Via web
# https://github.com/Vivaliz-site/site-shopvivaliz/settings/secrets/actions
```

#### Passo 4: VALIDAR nos 3 locais
```bash
# Local
grep "NOME_SECRET" C:\site-shopvivaliz\.env

# VM
ssh -i "$SSH_KEY" ubuntu@137.131.156.17 "grep NOME_SECRET /home/ubuntu/site-shopvivaliz/.env"

# GitHub
gh secret list --repo Vivaliz-site/site-shopvivaliz | grep NOME_SECRET
```

#### Passo 5: VERSIONAR VIA BRANCH, PR E MERGE
```bash
# Nunca versione o valor do secret. Inclua apenas arquivos permitidos que referenciem a mudança.
git switch -c chore/sync-nome-secret
git add <arquivos-versionados-sem-secrets>
git commit -m "chore: sincronizar referência de NOME_SECRET"
git push -u origin chore/sync-nome-secret
PR_URL=$(gh pr create --base main --head chore/sync-nome-secret --title "chore: sincronizar NOME_SECRET" --body "Sincronização validada sem versionar o valor do secret")
gh pr merge "$PR_URL" --squash --delete-branch
```

### Matriz de Sincronização

| Secret | Local | VM | GitHub | Notas |
|--------|-------|-----|--------|-------|
| **Database** | ✅ | ✅ | ❌ | Nunca em GitHub (risco) |
| **Email/SMTP** | ✅ | ✅ | ✅ | Seguro em GitHub |
| **APIs IA** | ✅ | ✅ | ✅ | Sincronizar sempre |
| **ERP/Commerce** | ✅ | ✅ | ✅ | Sincronizar sempre |
| **Deploy/FTP** | ✅ | ❌ | ✅ | Apenas Local+GitHub |
| **CloudFlare** | ✅ | ❌ | ✅ | Apenas Local+GitHub |

### O que Quebra se Não Sincronizar

| Cenário | Impacto | Severidade |
|---------|---------|-----------|
| **Atualizar só Local** | VM usa valor antigo → Erro 401 em produção | 🔴 CRÍTICO |
| **Atualizar só VM** | GitHub CI falha → Deploy quebrado | 🔴 CRÍTICO |
| **Atualizar só GitHub** | Local testa com valor errado | 🟡 MÉDIO |
| **Desatualizar 2/3** | Inconsistência impossível debugar | 🔴 CRÍTICO |

### SOS: Descobriu Desincronização?

**Ação imediata:**

```bash
# 1. Verificar qual está correto
gh secret list  # GitHub é fonte de verdade
ssh -i key.pem ubuntu@137.131.156.17 "grep NOME .env"  # Compare

# 2. Copiar do correto para os outros
# Se GitHub tá certo:
gh secret get NOME > valor.txt
scp valor.txt ...

# 3. Commitar estado correto
git commit -m "fix: sincronizar secrets desincronizados (SOURCE: GitHub)"
```

---

## 🛑 PROIBIÇÃO DE INFERÊNCIA

**Nunca conclua que algo ocorreu porque "deveria ter ocorrido". VERIFIQUE.**

❌ "O webhook foi enviado com sucesso" (sem ver log servidor)
❌ "A mudança deve ter sincronizado" (sem verificar SHA na VM)
❌ "Nenhum erro visto, então funcionou" (ausência ≠ sucesso)
❌ "O agente deve ter executado" (onde está o log?)
❌ "API respondeu 200, deve estar funcionando" (validar corpo também)
❌ "O visual/layout foi corrigido e está funcionando" (sem carregar no browser real e screenshot)

---

## 🔎 DESCONFIANÇA POR PADRÃO

**Antes de concluir sucesso, agente DEVE tentar provar que está ERRADO:**

1. **Como este teste pode estar me enganando?**
2. **Existe outra explicação para este resultado?**
3. **Eu mesmo provoquei o efeito que estou medindo?**
4. **Se fosse auditor externo, aceitaria esta evidência?**

**Se alguma pergunta não puder ser respondida, resultado DEVE ser INCONCLUSIVO.**

---

## 📝 TEMPLATE OBRIGATÓRIO DE RELATÓRIO

```markdown
# [Nome da Tarefa] - Relatório de Validação

**Data:** [ISO 8601]
**Agente:** [Nome]
**Resultado:** [COMPROVADO|FALHOU|INCONCLUSIVO]

## Evidência

### Preparação
- [ ] Estado inicial registrado
- [ ] Logs/métrica anterior capturada

### Disparo
- [ ] Mudança criada/enviada
- [ ] Confirmação de envio

### Espera
- [ ] Tempo suficiente para execução
- [ ] Sem intervenção manual

### Observação
- [ ] Método DIFERENTE de como foi disparado
- [ ] Comparação antes/depois
- [ ] Timestamps validados

## Dados Brutos
[Colar saída completa]

## Conclusão
[1-2 frases com evidência específica]

**Auditor Externo Aceitaria?** Sim / Não
```

---

## 📚 Referências Cruzadas

### Documentação Específica por Tópico

| Tópico | Arquivo | Escopo |
|--------|---------|--------|
| **Validação Geral** | Este arquivo (REGRAS-AGENTES-CENTRALIZADAS.md) | ✅ FONTE ÚNICA |
| **Princípios Gerais** | `docs/knowledge/agent-rules.md` | Fundamentos de diagnóstico |
| **Política de Imagens** | `docs/knowledge/image-policy.md` | Validação de imagens produtos |
| **Remote MCP** | `docs/AGENT-MCP-REMOTE.md` | Uso seguro de MCP remoto por agentes, sem publicar device code, device ID, e-mail completo ou tokens |

### Arquivos Deprecados

| Arquivo | Motivo | Ação |
|---------|--------|------|
| VALIDATION-POLICY.md | Conteúdo movido para este arquivo | ✅ Usar este arquivo em vez |
| SECRETS-SYNC-RULE.md | Conteúdo movido para Seção 6 | ✅ Usar este arquivo em vez |
| VALIDATION-RULES.md | Arquivo temporário da sessão anterior | ❌ Pode ser deletado |

---

## 🔄 Auditoria Semanal (Automática)

**Toda segunda-feira às 09:00 UTC:**

- [ ] Procurar novos arquivos `*-RULE.md` ou `*-POLICY.md` em raiz
- [ ] Confirmar que REGRAS-AGENTES-CENTRALIZADAS.md é FONTE ÚNICA
- [ ] Validar que docs/knowledge/* são apenas REFERÊNCIA
- [ ] Executar: `grep -r "NUNCA\|OBRIGATÓRIO\|PROIBIDO" . --include="*.md"` (detectar novas regras)
- [ ] Se encontrar novas regras: mover para este arquivo + criar entry em Referências Cruzadas

---

## 📞 Violações

**Se agente violar estas regras:**
1. Investigação e reorientação de agente
2. Registrar violação em CHANGELOG.md
3. Adicionar nova regra se necessário para evitar repetição

---

**Versão:** 2.0 (Consolidada)
**Atualizado:** 2026-07-24
**Próxima Revisão:** 2026-08-07
**Status:** ✅ FONTE ÚNICA DE VERDADE

## Gate obrigatorio de resposta final e deploy (FINAL_RESPONSE_DEPLOY_GATE_V1)

- A resposta final de conclusao e um gate operacional: nao pode ser enviada enquanto houver qualquer etapa executavel necessaria ao pedido original.
- Em alteracoes de codigo, configuracao ou documentacao versionada, PR aberto, checks verdes ou merge isoladamente NAO significam conclusao.
- Quando existir alvo de deploy para o repositorio, e obrigatorio acompanhar o deploy ate o SHA correto estar ativo e executar validacao pós-deploy real e reproduzivel.
- Se o deploy falhar, investigar a causa raiz, corrigir, revalidar, repetir commit/push/PR/merge quando necessario e tentar o deploy novamente; nao encerrar em estado intermediario.
- Antes de qualquer resposta final, comparar pedido original x estado real e registrar evidencias de: validacao, commit, push, PR, checks, merge, deploy e pós-deploy, conforme aplicavel.
- So e permitido encerrar sem deploy bem-sucedido diante de bloqueio externo genuino e incontornavel com os acessos/ferramentas disponiveis; nesse caso o estado e BLOCKED/INCONCLUSIVO, nunca sucesso.

## ISOLAMENTO OBRIGATORIO DE SESSAO CLI POR CHAT

- Cada chat/conversa deve possuir um namespace de sessao CLI exclusivo. E proibido reutilizar shell, REPL, terminal, PID, pane tmux/screen, sessao remota interativa ou identificador pertencente a outro chat.
- Antes do primeiro comando CLI, crie e registre um `CHAT_CLI_SESSION_ID` nao secreto e unico para o chat. Toda operacao CLI deve ser atribuivel a esse namespace.
- Por padrao, mantenha uma sessao CLI interativa ativa por chat. Se ela morrer ou ficar inutilizavel, crie uma substituta dedicada ao mesmo chat; nunca conecte o chat a sessao de outro chat.
- Subagentes podem usar processos filhos ou sessoes filhas apenas dentro do namespace do mesmo chat e nunca podem adotar sessao pertencente a outro chat.
- Antes de mutar arquivos, Git, infraestrutura ou sistemas externos, confirme identidade da sessao, diretorio atual, repositorio e branch/alvo.
- Memoria do shell nao e estado duravel. Persista retomada em repositorio, branch/commit, issue/tarefa ou checkpoint explicito para que um turno interrompido possa continuar sem emprestar a sessao CLI de outro chat.
- Todo processo em background iniciado por um chat deve ser rastreado por esse chat e encerrado quando nao for mais necessario, ou transferido explicitamente para um servico deterministico aprovado. Nao deixar processos orfaos nem sessoes interativas ocultas.
- Identificadores de sessao nao podem conter senhas, tokens, chaves, cookies, dados pessoais/sensiveis ou outros secrets.
- Ao terminar a tarefa, feche ou marque a sessao interativa do chat como concluida. Sessao concluida nunca pode ser reatribuida a outro chat.

Regra principal: **um chat = um namespace de sessao CLI isolado; nunca reutilizar sessao entre chats.**

## AUDITORIA_EXTREMA_ABSOLUTA_V5

A Auditoria Extrema global é fail-closed e inseparável de `AUDIT_BROWSER_E2E_REAL_V1`, `AUDIT_JOURNEY_INVENTORY_V1`, `AUDIT_CLEAN_ROOM_REALITY_V1`, `AUDIT_HARDENING_MAX_V1`, `AUDIT_APTO_REMEDIATION_LOOP_V1`, `AUDIT_ESCAPE_INVALIDATION_V1` e `AUDIT_ABSOLUTE_GATE_V1`.

- Se existe UI, o agente executa E2E real no browser da VM; API/CLI/headless-only não certificam.
- Tudo que impedir APTO e for executável deve ser corrigido pelo próprio agente, seguido de regressão, deploy quando aplicável e reauditoria.
- P0–P3, DEFECT, IMPROVEMENT_REQUIRED, AUDIT_ESCAPE, jornada/controle não validado e dívida material de evidência devem zerar.
- “Pré-existente” não isenta defeito dentro do escopo.
- Novo defeito descoberto após APTO invalida a certificação e vira prevenção permanente.
- APTO COM RESSALVAS é proibido no modo absoluto.
- O agente não escreve APTO por opinião: somente `scripts/certify-audit-manifest.py` com `AUDIT_VERDICT=APTO` para o mesmo SHA/release/ambiente/escopo.
- O conjunto canônico deve ser propagado com paridade para todos os repositórios ativos de `Vivaliz-site` e `fredmourao-ai`; divergência bloqueia governança.

## AUDITORIA_ARQUITETURA_DEPLOY_V1
Toda Auditoria Extrema deve incluir `docs/quality/ARCHITECTURE_DEPLOY_AUDIT_V1.md` e tratar melhorias arquiteturais materiais como parte da auditoria, inclusive tempo de deploy, runners, artifacts, cache, provisionamento, restarts, contratos cross-repo, hotspots, rollback e blast radius.


<!-- BROWSER_SESSION_POLICY_V1 -->
<!-- GLOBAL_BROWSER_VM_POLICY_V2 -->
## Politica global de navegador, host e ciclo de vida de sessoes

Esta politica vale para todos os agentes e prevalece sobre qualquer instrucao antiga de escolher/perguntar host para navegacao.

- Qualquer navegador, sessao grafica, automacao browser, Playwright/Selenium/CDP, Chrome/Chromium/Edge/Opera, CAPTCHA, MFA, consentimento ou validacao visual deve executar por padrao e obrigatoriamente na VM backend `always-free-arm-1787907847-26` (`10.0.1.38`) usando o Browser Worker privado.
- Para intervencao humana em MFA/CAPTCHA/consentimento, usar a interface autenticada `https://shopvivaliz.com.br/admin/browser-worker.php`.
- Fred-Win (`LAPTOP-NIG4IFUU`) e `DESKTOP-KOCEPSV` sao proibidos como destino ou fallback de navegacao/browser.
- O agente nao deve perguntar qual maquina usar para browser: o destino canonico e a VM backend. Excecao somente quando o proprietario ordenar explicitamente, na tarefa atual, o uso de um Windows especifico para aquela navegacao.
- Se a VM/browser worker estiver indisponivel, reparar via OCI Bastion, tunel privado ou control plane canonico; nunca fazer fallback silencioso para Windows.
- Workflows, scripts e bridges de browser que ainda apontem para Fred-Win/KOCEPSV sao legado e devem ser migrados antes do uso.
- Windows continua permitido para tarefas nao-browser que dependam especificamente de Windows/hardware local.
- Toda sessao invisivel/headless transitoria deve ter ownership rastreavel e TTL padrao de 2 horas renovavel por heartbeat; limpar recursos da tarefa ao concluir e nunca usar kill global por nome de processo.

Regra principal: **browser/navegacao sempre na VM backend; Windows nunca e fallback.**
