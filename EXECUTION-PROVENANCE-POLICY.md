# Politica obrigatoria de assinatura e origem de execucao

Esta politica e vinculante para agentes, workflows, scripts, servicos, timers, cron jobs, runners, bridges e comandos operacionais deste repositorio.

## Regra principal

Toda execucao material deve ter identidade e origem rastreaveis antes de alterar estado. Isso inclui deploy, migration, escrita em banco/API, criacao ou remocao de container/volume/worktree, alteracao de infraestrutura, automacao recorrente, execucao de IA e qualquer operacao privilegiada.

Cada execucao deve registrar, sem secrets:
- execution_id unico;
- timestamp_utc de inicio e fim;
- actor e agent/tool;
- origin_type: chat, github-actions, systemd, cron, cli, api, manual ou equivalente;
- origin_ref verificavel: run URL/id, session id, unit/timer, task id ou correlation id;
- repository, ref e sha quando aplicavel;
- host, pid e parent_execution_id quando aplicavel;
- trigger, action e target;
- result e exit_code;
- cleanup_status para recursos temporarios;
- payload_sha256 do registro canonico;
- signature_id correlacionando executor, origem, execution id e digest.

Quando existir identidade criptografica provisionada, assinar o payload com HMAC, Ed25519 ou attestation equivalente e registrar somente a assinatura e o identificador da chave, nunca a chave. Acoes privilegiadas de producao devem usar assinatura criptografica ou identidade/attestation de plataforma equivalente. Se indisponivel, registrar signature_status=UNSIGNED e nao declarar a execucao como verificada.

## GitHub Actions

Usar os identificadores nativos como origem: GITHUB_ACTOR, GITHUB_REPOSITORY, GITHUB_SHA, GITHUB_REF, GITHUB_RUN_ID, GITHUB_RUN_ATTEMPT, GITHUB_JOB e URL do run. Service containers, volumes e outros recursos temporarios devem ser associados ao execution_id e limpos ao final, inclusive em cancelamento/falha.

## Agentes e CLI

O agente deve preservar o identificador da conversa/sessao e da tarefa. Comandos que criam processos, containers, volumes, worktrees, branches, PRs, arquivos ou efeitos externos devem registrar a origem antes da acao e o resultado depois. Nao atribuir a terceiros uma acao que o proprio agente disparou.

## Recursos temporarios e prevencao de orfaos

Todo recurso temporario deve conter owner/origin quando a plataforma permitir labels, tags ou nome, e possuir cleanup explicito. Recursos anonimos sem owner nao podem ser adotados como padrao em rotinas novas. Em incidente, preservar evidencia minima: ids, timestamps, origem, tamanho e digest antes da limpeza.

## Segredos

E proibido registrar token, senha, cookie, seed/OTP, chave privada ou conteudo de secret. Use apenas nomes de secret/key ids e referencias seguras.

## Validacao

Execucao sem origem suficiente e UNATTRIBUTED; sem assinatura/attestation exigida e UNSIGNED; sem evidencia de efeito e INCONCLUSIVE. Nenhum desses estados pode ser promovido a VERIFIED.

Use scripts/emit-execution-provenance.py como formato de referencia para registros estruturados.
