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

HTTP 2xx/3xx também não é sucesso quando a pós-condição estiver errada, ausente, stale ou parcialmente aplicada. Falha silenciosa bloqueia o fluxo da mesma forma que uma exceção explícita.

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

Aplique `AUDIT_EVIDENCE_FRESHNESS_V1`: a evidência deve corresponder ao mesmo SHA/build/digest, ambiente e configuração material do release certificado. Evidência stale, de outro ambiente ou sem timestamp/proveniência é dívida de evidência.

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
- área crítica marcada `NÃO VALIDADO`;
- P0/P1, P2 crítico ou `IMPROVEMENT_REQUIRED` crítico pendente;
- classe de `AUDIT_ESCAPE` aplicável ainda sem correção/prevenção/reauditoria;
- automação assíncrona crítica não observada no release certificado quando material ao fluxo;
- efeito externo sem reconciliação independente;
- proteção de observabilidade crítica existente apenas no papel, sem prova de detecção equivalente quando tecnicamente viável;
- rollback/restore necessário ao risco da mudança sem evidência compatível;
- evidência crítica stale, de SHA/ambiente diferente ou sem proveniência;
- fluxo material sem negativos/boundaries aplicáveis exercitados;
- reconciliação de dados com diferença inexplicada;
- entidade órfã/estado eterno material sem owner e recuperação;
- teste flaky/falso-verde sustentando conclusão;
- regressão material de baseline não investigada;
- classe material da taxonomia universal marcada `NÃO VALIDADO`;
- rodada de unknown unknowns omitida em auditoria extrema;
- self-test obrigatório do mecanismo de auditoria ausente ou falhando.

O veredito deve continuar sendo `NÃO APTO` ou `APTO COM RESSALVAS` conforme risco e evidência, nunca mascarando dívida de validação.

## 9. Reauditoria contraditória

Depois das correções, repita os fluxos tentando quebrá-los com outro registro/estado, edge/failure path e nova navegação. O objetivo não é provar que o patch passa; é tentar provar que a conclusão de correção está errada.

## 10. Observação pós-deploy e reconciliação
Para release publicado, valide também o comportamento que acontece depois da ativação inicial. Workers, filas, schedulers, webhooks e integrações críticas devem ter ao menos uma execução produção-equivalente comprovada no mesmo SHA/release, por ciclo natural ou disparo controlado seguro. Registre início, término, estado antes/depois, efeito durável e reconciliação.

## 11. Prova da observabilidade
Quando uma classe de falha crítica depende de healthcheck, watchdog, alerta, dead-letter, métrica ou log para ser detectada, prove o detector com falha controlada segura ou evidência operacional equivalente. Detector configurado mas nunca exercitado é dívida de evidência.

## 12. Recuperação e rollback
Mudança crítica que possa exigir reversão deve ter caminho de rollback/restore compatível com schema, eventos, filas, caches e dados. Prefira ensaio em staging/preview/clone consistente quando a reversão real em produção for arriscada ou destrutiva.

## 13. Legado e duplicidade no runtime
Compare o release certificado com processos realmente ativos. Procure serviço, cron, timer, workflow, runner, consumer, bridge, script ou automação antiga que ainda possa executar a mesma responsabilidade, produzir efeito concorrente ou mascarar a validação do caminho novo.

## 14. Falha silenciosa e ausência de produção
Runtime parity deve verificar não só erros emitidos, mas também trabalho que deixou de acontecer. Compare contagens/efeitos esperados, freshness de dados, consumo de fila, produção de eventos, atualizações de timestamp e reconciliação. Ausência inesperada de evento/efeito é falha mesmo com zero exceções.

## 15. Negativos, boundaries e ambientes
Para operações críticas, a evidência publicada deve cobrir os negativos/boundaries materiais e combinações de ambiente que possam mudar o comportamento. A seleção pode ser risk-based, mas deve estar explícita.

## 16. Baseline operacional
Quando a mudança puder afetar capacidade/custo, compare métricas do release com baseline válido. Aumento material de erro, latência, memória, filas, chamadas externas ou custo deve ser investigado antes do veredito.

**Marker de governança:** `AUDIT_RUNTIME_PARITY_V1`
