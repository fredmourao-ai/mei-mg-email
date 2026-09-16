# Estado da Auditoria

**Status:** NÃO APTO

Nova auditoria formal executada em 2026-09-16 segundo `EXTREME_AUDIT_PROTOCOL.md`, `AUDIT_RUNTIME_PARITY_V1.md`, a matriz obrigatória de transições/estado histórico e o overlay do projeto.

## Última auditoria válida
- Data: 2026-09-16.
- Commit/SHA auditado: `62cf556a4ce7486fc1f32cb12da942a05febd430`.
- Runtime observado: checkout produtivo em `83d24abfa9e5c2712e35455f6c38e0d182182f37`, com working tree modificado e arquivo/diretório não versionado.
- Veredito: **NÃO APTO PARA CERTIFICAÇÃO**.
- Confiança: alta.
- Stop-the-line: o runtime real não corresponde ao SHA auditado e não é uma árvore imutável; restore integral continua sem prova reexecutável.

## Evidência fresca desta auditoria
- `mei-mg-email-worker.service`, completion monitor, delivery reconciler e watchdog foram observados ativos.
- Processos operacionais observados: API/Uvicorn, `monitor_operacao`, `queue_replenisher`, `safe_entrypoint_v2` e `brevo_event_reconciler`.
- Não apareceram erros correspondentes no recorte recente do journal do worker usado nesta inspeção.
- A tentativa explícita de `GET http://127.0.0.1:8010/health` retornou `404`, portanto esse caminho não pode ser usado como prova de health atual sem contrato adicional.
- O checkout produtivo continha modificações locais em units/scripts operacionais e conteúdo não versionado. Assim, `commit -> build -> deploy -> processo ativo` não é demonstrável para o SHA auditado.
- O `main` possui os gates de governança da nova regra, mas um gate verde de repositório não substitui execução produção-equivalente.

## Matriz de operação e paridade
| Operação / superfície | Evidência local/CI | Evidência no runtime auditado | Resultado |
| --- | --- | --- | --- |
| fila -> worker | cobertura/testes históricos + processo ativo | processos ativos observados | PARCIAL |
| worker -> provedor | coberto por contratos/testes do projeto | nenhum envio novo foi provocado nesta auditoria | NÃO REVALIDADO E2E |
| eventos Brevo -> reconciliação | reconciler implementado/ativo | processo ativo observado | PARCIAL |
| rate limit / fail-closed | cobertura histórica | não foi induzido evento mutável real | NÃO REVALIDADO |
| supressão/NDR | cobertura histórica | sem canário seguro novo | NÃO REVALIDADO |
| restart/retry/idempotência | testes existentes | não reproduzidos no checkout produtivo divergente | NÃO VALIDADO NO RELEASE |
| backup -> restore | backup/integridade já documentados | restore integral isolado não comprovado | FAIL / DÍVIDA DE EVIDÊNCIA |
| SHA exato -> runtime | n/a | `62cf556a...` != `83d24ab...` + árvore suja | **FAIL** |

## Achados
### P1 — runtime sem proveniência imutável
**COMPROVADO.** O SHA auditado é `62cf556a...`; o checkout em execução é `83d24ab...` e possui alterações locais/untracked. Sob `AUDIT_RUNTIME_PARITY_V1`, não é permitido atribuir o comportamento observado ao release candidato.

### P1 — recuperação integral ainda não comprovada
A auditoria anterior comprovou criação/integridade remota de backup, mas não restore completo com validação dos invariantes. A nova regra mantém esse ponto como bloqueador para dado crítico.

### P2 — health endpoint observado diverge da evidência histórica
`/health` na porta 8010 retornou 404 nesta inspeção. Isso pode significar mudança de contrato/rota, e não queda da API, mas a evidência histórica de health 200 não deve ser reutilizada como se fosse atual.

### P2 — paridade operacional incompleta
Fila, worker e reconciler estavam ativos, porém não foi disparado envio real por segurança. Não existe nesta auditoria uma trilha completa `entrada -> submissão -> confirmação -> reconciliação` no mesmo release que está em produção.

## Risco residual
Alto para certificação, mesmo com serviços operacionais ativos. A maior dívida é atribuição: não há release imutável correspondente ao `main`, e recuperação integral do dado não foi reproduzida.

## Saída do NO-GO
1. eliminar drift/alterações locais e implantar artefato imutável identificado por SHA;
2. expor/validar health canônico versionado do runtime;
3. executar canário seguro produção-equivalente com confirmação e reconciliação sem aumentar campanha;
4. executar restore integral isolado e medir RPO/RTO;
5. repetir transições/retries em dados atuais e históricos e reauditar contraditoriamente.

## Regra de validade
Esta auditoria cobre o SHA `62cf556a4ce7486fc1f32cb12da942a05febd430` e o runtime observado em 2026-09-16. Qualquer mudança material em provider, elegibilidade, fila, cota, banco, reconciliação ou deploy exige reauditoria.