# AUDIT_RUNTIME_PARITY_V1 — Regra Global de Auditoria de Operação Real

Esta regra é **obrigatória e inseparável** de `AUDIT_POLICY.md` e `docs/quality/EXTREME_AUDIT_PROTOCOL.md` em toda auditoria formal, validação de release ou declaração de sistema pronto/apto. Ela existe para impedir falso positivo de auditoria em que um fluxo funciona em teste local, mas falha no ambiente realmente publicado.

## 1. Regra de equivalência operacional

Uma tela carregada, um healthcheck verde, HTTP 200, teste unitário/integrado ou um fluxo local bem-sucedido **não certifica** o comportamento publicado.

Para cada operação aplicável do sistema, monte e execute a matriz:

`operação → cobertura local → cobertura staging/preview/publicada → execução real → persistência/efeito → evidência`

Operações incluem, conforme o domínio: `Create`, `Read`, `Update`, `Delete`, `Archive`, `Restore`, `Cancel`, `Reopen`, `Retry`, `Undo`, `Approve`, `Reject`, `Confirm`, `Send`, `Charge`, `Refund`, `Appeal`, `Reconcile`, `Import`, `Export`, `Deploy` e `Rollback`.

Fluxo crítico presente na suíte local, mas ausente da homologação executada contra o ambiente/release certificado, é **DÍVIDA DE EVIDÊNCIA** e bloqueia `APTO`.

## 2. UI real é obrigatória quando existe UI

Quando o produto possui interface de usuário, toda operação crítica ou de alteração de estado deve ser exercitada pela **UI real** no navegador contra o mesmo release/ambiente que está sendo certificado. API, SQL, fixtures e scripts podem preparar dados ou verificar o efeito, mas não substituem a ação do operador na UI.

A auditoria deve cobrir tanto dados recém-criados quanto registros já existentes/legados quando essa diferença puder alterar o comportamento.

Após cada mutação:
1. confirme o feedback imediato da UI;
2. recarregue a página;
3. navegue para fora e retorne ao registro;
4. confirme que o estado persistiu na UI;
5. quando autorizado, confirme também banco/fila/API/efeito externo durável;
6. valide histórico/auditoria/reconciliação quando aplicável.

## 3. Gate fatal de erros de navegador e servidor

Em E2E/homologação de aplicações web, qualquer ocorrência inesperada abaixo reprova o fluxo e a auditoria até investigação:

- resposta HTTP `5xx` de aplicação;
- `pageerror`/exceção não tratada;
- `requestfailed` inesperado;
- `console.error` inesperado;
- tela de erro de framework/proxy/servidor, inclusive mensagens equivalentes a `This page couldn't load`;
- navegação ou Server Action que termina em erro mesmo que a página anterior tenha carregado corretamente.

Exceções só podem existir em allowlist **estreita, versionada e justificada**, contendo origem, motivo, impacto e teste que demonstra por que o evento é esperado. Allowlist genérica é proibida.

Respostas `4xx` só são sucesso quando o próprio caso de teste é negativo e comprova que aquele `4xx` é o comportamento esperado.

## 4. Paridade local × ambiente publicado

Antes do veredito, gere inventário dos testes/fluxos operacionais locais e compare com os realmente executados em staging/preview/publicação.

É proibido certificar produção executando apenas um subconjunto “representativo” se esse subconjunto omite operação crítica existente na suíte local. Se a suíte externa precisar ser menor, a exclusão de cada fluxo deve ser explícita e o fluxo deve receber evidência equivalente no mesmo release.

A homologação deve confirmar que o SHA/build/digest esperado é o efetivamente servido pelo ambiente testado. Sem proveniência do release, marque `VERSÃO EM PRODUÇÃO NÃO COMPROVADA`.

## 5. Evidência mínima por fluxo

Para cada fluxo crítico registre, quando tecnicamente aplicável:

- SHA/release/build e ambiente;
- entidade/registro utilizado;
- passos reproduzíveis;
- resultado antes/depois;
- screenshot/trace de falha ou sucesso relevante;
- rede/status HTTP;
- logs/correlation ID do backend;
- persistência ou efeito externo confirmado;
- teste automatizado correspondente;
- resultado da reexecução contraditória.

“Não encontrei erro” sem essa trilha não é evidência de correção.

## 6. Projetos sem UI

Serviços API-only, workers, pipelines e automações devem aplicar a mesma regra usando sua interface operacional canônica: endpoint real, fila, scheduler, webhook, CLI operacional ou job publicado. Mock isolado ou chamada de função interna não substitui o caminho real de produção-equivalente.

Valide `entrada → persistência → processamento → efeito → confirmação → reconciliação`, inclusive timeout, retry, idempotência, duplicação, restart e falha parcial quando aplicáveis.

## 7. AUDIT_ESCAPE — falha descoberta depois de auditoria

Quando um usuário/operador encontra manualmente, após uma auditoria, um defeito que deveria ter sido detectado pelo escopo declarado:

1. registre como `AUDIT_ESCAPE`;
2. reproduza e encontre a causa funcional **e a causa do falso negativo da auditoria**;
3. identifique a **classe de falha** ausente, não apenas o caso específico;
4. procure a mesma classe em rotas, operações e módulos equivalentes;
5. atualize o protocolo/regra global quando a lacuna for sistêmica;
6. reaudite a classe afetada nos demais projetos onde ela seja aplicável;
7. invalide qualquer certificação incompatível com a nova evidência até a revalidação.

## 8. Gate de conclusão

Um projeto não pode receber `APTO` quando existir qualquer uma destas condições:

- operação crítica não executada no ambiente/release certificado;
- cobertura crítica local sem evidência equivalente no ambiente publicado;
- `5xx`, `pageerror`, `requestfailed` ou `console.error` inesperado sem causa resolvida;
- mutação sem confirmação após reload/revisita;
- efeito externo sem confirmação/reconciliação;
- versão realmente publicada não comprovada;
- área crítica marcada `NÃO VALIDADO`.

O veredito deve continuar sendo `NÃO APTO` ou `APTO COM RESSALVAS` conforme risco e evidência, nunca mascarando dívida de validação.

## 9. Reauditoria contraditória

Depois das correções, repita os fluxos tentando quebrá-los com outro registro/estado, edge/failure path e nova navegação. O objetivo não é provar que o patch passa; é tentar provar que a conclusão de correção está errada.

**Marker de governança:** `AUDIT_RUNTIME_PARITY_V1`
