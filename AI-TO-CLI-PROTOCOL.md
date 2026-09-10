# Protocolo Canônico IA-to-CLI

**Versão:** 2026-09-09  
**Escopo:** toda IA/agente que leia, analise, altere, valide, faça commit, PR, merge, deploy ou opere infraestrutura deste projeto.

Esta política é obrigatória e complementar às regras específicas do repositório. Em conflito, prevalece: instruções de segurança/plataforma > regras organizacionais/legais > regras específicas do projeto/AGENTS/ADR > este protocolo > instrução da tarefa. Nunca reduza segurança, privacidade, integridade de dados ou proteções do repositório para cumprir uma regra inferior.

## 1. Raciocínio e contexto

- Para decisões, bugs, arquitetura e mudanças de risco, use o maior esforço de raciocínio disponível e adequado à complexidade; mudanças mecânicas não precisam do modelo mais caro.
- Antes de alterar, entenda arquitetura, dependências, segurança, regras de negócio e padrões existentes. Não refatore fora do escopo.
- Nunca presuma que o repositório permaneceu inalterado desde a última leitura.

## 2. Pre-flight obrigatório

Antes da primeira escrita:

1. registrar repositório, branch, HEAD/base SHA e arquivos pretendidos;
2. verificar estado Git e trabalho concorrente; preservar alterações alheias;
3. ler os arquivos e instruções aplicáveis imediatamente antes do patch;
4. executar baseline focal quando houver teste relevante, para separar falha preexistente da introduzida pela tarefa;
5. para produção/deploy, identificar antecipadamente a versão saudável e o rollback possível.

Antes de **cada** escrita, revalidar HEAD, arquivo-alvo e trecho-alvo. Se mudaram, invalidar o patch antigo, reler e recalcular. Nunca sobrescrever silenciosamente trabalho concorrente.

## 3. Edição cirúrgica obrigatória

Arquivos existentes não devem ser reescritos integralmente para uma mudança localizada. Use mudança mínima e formato SEARCH/REPLACE quando o executor suportar:

```diff
File: caminho/do/arquivo.ext
<<<<<<< SEARCH
[no mínimo 2 linhas exatas de contexto inalterado acima]
[trecho literal atual]
[no mínimo 2 linhas exatas de contexto inalterado abaixo]
=======
[mesmo contexto acima]
[novo trecho]
[mesmo contexto abaixo]
>>>>>>> REPLACE
```

Regras do patch:

- SEARCH é literal: sem `...`, pseudocódigo, abreviação ou contexto inventado.
- Cada SEARCH deve encontrar **exatamente 1 ocorrência**. Se encontrar 0 ou >1, abortar esse patch, reler o arquivo e gerar outro bloco.
- Mudanças independentes usam blocos separados; imports/requires/dependências novas exigem bloco dedicado no topo/manifesto.
- Não alterar encoding, BOM, CRLF/LF, permissões, ownership ou formatação não relacionada.
- Não editar artefato gerado (`dist`, `build`, bundles, código gerado, lock derivado) quando existir fonte de verdade; alterar a fonte e regenerar.
- Nunca usar refatoração, formatter global ou upgrade incidental para esconder a mudança real.

### Arquivo novo

CREATE só é permitido quando o caminho realmente não existe. Se existir, abortar. É proibido usar CREATE para contornar SEARCH/REPLACE. Arquivos novos grandes devem ser criados incrementalmente quando tecnicamente viável.

## 4. Dependências e contratos

- Antes de adicionar biblioteca, provar que a stack existente não resolve adequadamente; verificar manutenção, compatibilidade, licença e segurança.
- Manifesto e lockfile devem mudar juntos pela ferramenta oficial; lockfiles não são editados manualmente salvo formato que explicitamente suporte isso.
- Mudanças em API, evento, banco, CLI, env, JSON ou contrato público exigem busca dos consumidores e preferência por compatibilidade retroativa.
- Migrations são forward-safe, testáveis e com estratégia de rollback/restore; não alterar migration já aplicada quando o projeto proíbe isso.

## 5. TDD e validação em camadas

Para bug/feature, quando tecnicamente aplicável: reproduzir com teste que falha antes, implementar o mínimo e provar que passa depois. Não inventar teste inútil só para cumprir cerimônia.

Validar proporcionalmente ao risco nesta ordem:

1. sintaxe/typecheck/lint aplicável;
2. teste focal que cobre a mudança;
3. testes do módulo/integração relevante;
4. suíte completa quando escopo/risco justificar ou a regra do projeto exigir;
5. smoke funcional real;
6. smoke visual/produção quando aplicável.

Nunca “fazer ficar verde” enfraquecendo teste, assertion, lint, type safety, segurança, CI, guard, RLS, autenticação ou feature gate. Alterar o sistema de validação só quando a própria tarefa exigir explicitamente essa mudança.

Se um teste falhar e depois passar sem mudança, tratar como potencialmente flaky; não usar a segunda passagem isolada como prova. Compare com baseline.

## 6. Self-healing disciplinado

- Ao falhar lint/test/build/smoke, ler o erro e corrigir a causa; repetir a validação.
- Fazer pelo menos duas tentativas autônomas razoáveis antes de pedir ajuda quando a falha for corrigível pelo agente.
- Depois de duas correções fracassadas, a terceira alteração só pode ocorrer com hipótese de causa raiz sustentada por log, stack trace, reprodução, diff ou teste. Nada de tentativa aleatória.
- Não mascarar erros com `|| true`, `exit 0`, redirecionamento que esconda falha, `--force`, catch genérico silencioso ou bypass de proteção.
- Falha preexistente fora do escopo deve ser demonstrada contra baseline; não ampliar silenciosamente a tarefa para “zerar tudo”.

## 7. Segurança e dados sensíveis

- Nunca colocar secrets, tokens, cookies, senhas, chaves privadas, seed/TOTP, dados pessoais sensíveis ou credenciais em diff, commit, PR, logs ou saída de teste.
- Evitar secrets em argumentos de processo/histórico/lista de processos; usar secret store, stdin protegido ou mecanismo equivalente e redaction.
- Não desabilitar autenticação, autorização, RLS, MFA, sandbox, branch protection ou controles de segurança para completar a tarefa.
- Antes do commit, revisar diff para secrets, debug temporário, arquivos inesperados e mudanças fora do escopo.

## 8. Efeitos externos, idempotência e produção

- E-mail, cobrança, publicação, marketplace, ticket, SAFE-T/recurso, deploy ou qualquer efeito externo deve ser idempotente ou verificar se a tentativa anterior já produziu efeito antes de retry.
- Um HTTP 200 sozinho não prova sucesso; smoke deve verificar o comportamento/estado real alterado.
- Para mudança de risco em produção, rollback e alvo saudável devem existir antes do deploy. Se smoke de produção falhar e rollback for seguro/aplicável, restaurar a versão saudável e investigar.
- Registre o ambiente relevante de validação (runtime/versão/SO/container) quando puder afetar o resultado.

## 9. Concorrência multiagente

- Use controle otimista por SHA/estado, não “lock eterno”.
- Mudança de outro agente no mesmo trecho invalida o patch; reaplique sobre a versão nova. Mudança não relacionada deve ser preservada.
- Nunca resolver concorrência com `git reset --hard`, `git checkout -- .`, `git clean -fd[x]`, force-push ou operação destrutiva equivalente.
- Registre metadados mínimos da tarefa: agente/tarefa, base SHA e arquivos pretendidos, sem secrets.
- Se a correção inicialmente pequena crescer para muitos arquivos, dependências ou subsistemas, reavaliar causa raiz e decompor antes de expandir escopo.

## 10. Merge obrigatório — nenhuma alteração válida abandonada

**Commit, push e PR não são estado final.** Todo trabalho válido/intencional produzido pela tarefa deve chegar à branch de destino por merge validado.

Fluxo obrigatório para alteração versionada:

`branch isolada -> alteração -> validação -> commit -> push -> PR -> checks/revisão -> correções -> merge -> validação pós-merge -> limpeza do estado intermediário`

É proibido concluir deixando alteração válida em:

- working tree ou arquivo não rastreado;
- stash;
- commit apenas local;
- branch não publicada;
- worktree órfão;
- PR draft/aberta/verde aguardando alguém “terminar depois”;
- commit órfão ou cherry-pick/merge incompleto.

Não mesclar código quebrado apenas para cumprir a regra. Tentativas experimentais que falharam não são entrega: reverta-as explicitamente e preserve evidência útil; não as abandone ambiguamente. Se houver bloqueio externo real após esgotar correções seguras, manter o trabalho recuperável e reportar exatamente o gate bloqueador — nunca apagar trabalho válido nem declarar conclusão.

Após merge, confirmar que a branch de destino contém o conteúdo/SHA esperado e que não existe PR pendente da mesma rodada. Se houver deploy automático aplicável, acompanhar o gate e validar o comportamento real antes de concluir.

## 11. Evidência antes de conclusão

Antes de afirmar “corrigido”, “funcionando”, “verde”, “deployado” ou “concluído”:

- executar verificação fresca que prove a afirmação;
- revisar o diff final (`git diff --check` ou equivalente quando disponível);
- confirmar arquivos esperados e ausência de debug/temp/secrets;
- confirmar testes/checks aplicáveis sem falhas novas;
- confirmar merge e pós-merge;
- confirmar produção quando a tarefa inclui produção.

Registro final mínimo: branch, SHA/base inicial, SHA/merge final, arquivos alterados, validações executadas, resultado e deploy/rollback quando aplicável. Não despejar logs gigantes ou dados sensíveis.

## 12. Regra de ouro

**Evidência antes de afirmação; preservação antes de sobrescrita; causa raiz antes de tentativa; merge validado antes de conclusão.**

## Isolamento obrigatorio de sessao CLI por chat

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
