# AUDIT_CLEAN_ROOM_REALITY_V1 — Sessão limpa, cold start, concorrência e recuperação

Esta regra reduz falsos-verdes que aparecem apenas porque a auditoria usou uma sessão perfeita, cache aquecido ou sequência ideal.

## CLEAN_ROOM_SESSION_V1 — sessão e autenticação
Quando material, exercite: contexto limpo sem cookies/storage; cache frio; usuário não autenticado; login real; sessão válida; sessão expirada/revogada; logout/login; deep-link protegido; role sem permissão; troca de tenant/owner. Preserve perfis canônicos, mas use contexto de teste separado para cenários destrutivos de sessão.

## Cache, PWA e navegação
Valide reload normal, hard reload quando aplicável, service worker/cache antigo versus release nova, assets versionados, back/forward, refresh no meio do fluxo, deep-link, nova aba e retorno após redirect externo. Conteúdo stale incompatível com a release ativa bloqueia `APTO`.

## Viewport, engine e acessibilidade
Para UI responsiva, cubra no mínimo desktop e mobile. Quando diferenças de engine forem materiais, cubra browser alternativo disponível. Para controles críticos, valide teclado, foco, Enter/Space, labels/nomes acessíveis, modal focus/escape e mensagens de erro associadas.

## CONCURRENCY_REALITY_V1 — concorrência e idempotência
Quando material, exercite duplo clique, submit repetido, duas abas, duas sessões, retry após timeout, evento duplicado/fora de ordem e refresh durante processamento. Prove ausência de duplicidade, lost update, corrupção e estado impossível.

## PARTIAL_FAILURE_RECOVERY_V1 — falha parcial e recuperação
Em ambiente seguro apropriado, injete perda de rede, provider indisponível, restart de worker/processo e falha após persistência parcial. Prove retry/backoff, idempotência, compensação, retomada, alerta e reconciliação.

## COLD_START_RUNTIME_V1 — cold start
Quando material, valide primeira execução após deploy/restart, cache/pool ainda frios e worker recém-iniciado. Dependência de aquecimento ou intervenção manual não documentada é finding.

## Tempo
Para regras temporais, exercite antes/no/depois do limite, timezone material, expiração de sessão/token, jobs atrasados e eventos fora de ordem quando simuláveis com segurança.

## Soak e vazamento
Para processos recorrentes/long-lived, rode duração suficiente para revelar crescimento anormal de memória, fila, handles, conexões, disco, logs, retries ou custo. A duração deve ser proporcional ao risco e ao ciclo operacional, não um número fixo arbitrário.

## Gate
Cenário material desta regra não exercitado = `NÃO VALIDADO`. Falha descoberta reabre o `AUDIT_APTO_REMEDIATION_LOOP_V1`.

**Marker de governança:** `AUDIT_CLEAN_ROOM_REALITY_V1`
