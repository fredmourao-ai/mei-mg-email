# AUDIT_UNIVERSAL_COVERAGE_V1 — Cobertura Universal e Caça a Falhas

Esta regra é obrigatória em toda Auditoria Extrema. Ela existe para reduzir pontos cegos, detectar falhas silenciosas e impedir que a auditoria dependa apenas de bugs já conhecidos.

## 1. AUDIT_EVIDENCE_FRESHNESS_V1 — validade da evidência
Toda evidência usada para certificar um release deve estar vinculada a `SHA/build/digest + ambiente + timestamp + fluxo/entidade`.
- Evidência de outro SHA, ambiente ou configuração não certifica o release atual.
- Evidência antiga só pode ser reutilizada para propriedades realmente imutáveis e com justificativa explícita.
- Mudança material invalida a evidência das áreas impactadas.
- Evidência sem proveniência é `DÍVIDA DE EVIDÊNCIA`.

## 2. AUDIT_CHANGE_IMPACT_V1 — mapa de impacto antes de testar
Antes dos testes, monte `mudança → dependentes → fluxos → dados → integrações → riscos → testes/evidências necessários`.
Considere imports/callers, banco/schema, contratos, filas, jobs, cache, UI, feature flags, configuração, deploy, observabilidade, rollback e consumidores externos.
Dependente material não mapeado = cobertura incompleta.

## 3. AUDIT_NEGATIVE_PATH_MATRIX_V1 — matriz de falhas
Para cada fluxo crítico, exercite conforme aplicável:
`happy path | input inválido | ausente/null | zero/negativo | limite/máximo | duplicado | concorrente | timeout | 429 | 4xx | 5xx | resposta parcial | resposta malformada | evento atrasado | fora de ordem | retry | restart | perda de conexão | dependência indisponível | permissão negada | storage cheio | quota esgotada`.
Caso material não exercitado deve aparecer como `NÃO VALIDADO`.

## 4. AUDIT_BOUNDARY_MATRIX_V1 — limites e off-by-one
Teste fronteiras numéricas, de tamanho e de tempo: `-1/0/1`, mínimo/máximo, vazio/um/muitos, exatamente no limite, imediatamente antes/depois, T-1/T/T+1, DST/timezone, virada de dia/mês/ano, precisão/rounding de moeda, encoding e Unicode.
Procure overflow/underflow, truncamento, arredondamento incorreto e off-by-one.

## 5. AUDIT_DATA_RECONCILIATION_V1 — fechamento contábil de dados
Fluxo crítico com dados persistidos ou efeitos externos deve provar `origem → processamento → destino → confirmação → reconciliação independente`.
Use contagens, somatórios, hashes ou invariantes de conservação quando aplicável. Exemplo: `entradas = concluídas + pendentes justificadas + falhas conhecidas`.
Diferença sem explicação é achado, não ruído.

## 6. AUDIT_ORPHAN_DETECTION_V1 — entidades perdidas
Procure automaticamente registros que entram no funil e não chegam a estado terminal válido: órfãos, estados eternos, outbox sem consumo, fila sem owner, evento sem entidade, pedido sem fechamento, reembolso sem crédito, devolução sem reconciliação, job sem conclusão, arquivo sem referência e recurso sem cleanup.
Ausência de detector para órfãos materiais é `IMPROVEMENT_REQUIRED`.

## 7. AUDIT_SILENT_FAILURE_V1 — erro sem exceção
Audite falhas que retornam 2xx/verde mas produzem resultado errado, incompleto, stale ou omitido:
- valor incorreto, arredondamento errado ou default silencioso;
- efeito externo não realizado;
- cache desatualizado;
- campo omitido;
- fallback que mascara indisponibilidade;
- fila aceita mas não consumida;
- rotina que para de produzir;
- métrica/health que permanece verde sem trabalho real.
Sucesso técnico sem pós-condição correta é falha.

## 8. AUDIT_DIFFERENTIAL_METAMORPHIC_V1 — procurar erro sem oracle perfeito
Quando o resultado correto não for trivial, use comparação independente: versão anterior, fonte oficial, implementação redundante, cálculo alternativo, replay, property-based, invariantes metamórficos ou dupla leitura.
Exemplos: ordenar entrada não deve alterar total; retry idempotente não deve duplicar efeito; soma das partes deve reconciliar com total; round-trip serialize/deserialize deve preservar semântica.

## 9. AUDIT_FLAKY_FALSE_GREEN_V1 — testes não confiáveis não contam
Teste flaky, skipped sem justificativa, assert inútil, mock que elimina o comportamento crítico, timeout mascarado, `continue-on-error`, exit code ignorado ou retry que converte defeito determinístico em verde não pode sustentar `APTO`.
A auditoria deve perguntar: **se o produto estivesse quebrado, este teste realmente falharia?**

## 10. AUDIT_EXTERNAL_ACTION_SAFETY_V1 — efeitos externos
Ação financeira, comunicação, publicação, alteração de pedido/estoque/reembolso/claim ou outro efeito externo deve provar conforme aplicável:
`dry-run/sandbox → autorização → idempotency key/deduplicação → execução → confirmação → reconciliação → compensação/recovery`.
Nunca confunda request aceita com efeito realizado.

## 11. AUDIT_BASELINE_REGRESSION_V1 — deterioração também é defeito
Compare baseline quando material: latência, throughput, memória, CPU, disco, conexões, filas, erro, custo, chamadas de API, logs, tamanho de payload/banco, taxa de sucesso e tempo de conclusão.
Regressão material sem justificativa deve ser classificada e investigada mesmo que funcionalmente ainda “passe”.

## 12. AUDIT_OWNERSHIP_DEADLINE_V1 — nada pode esperar para sempre
Estado pendente material deve ter `owner + condição/prazo + detector de vencimento + ação/alerta + recuperação`.
“aguardando”, “pending”, “processing” ou equivalente sem saída verificável é achado.

## 13. AUDIT_ENVIRONMENT_MATRIX_V1 — ambiente e compatibilidade
Quando aplicável, cubra combinações materiais de browser/device/viewport, SO/runtime, versão de API/schema, tenant/role/permissão, locale/timezone, configuração/feature flag e dados novos/legados.
Não é exigido testar combinações sem relevância material, mas a seleção deve ser justificada.

## 14. AUDIT_ERROR_TAXONOMY_V1 — taxonomia universal mínima
Toda auditoria deve considerar explicitamente, e marcar `N/A` com justificativa quando não aplicável:
1. lógica/regra de negócio/cálculo;
2. dados/integridade/schema/migration/histórico;
3. estado/lifecycle/transições;
4. concorrência/race/idempotência/duplicação;
5. tempo/data/timezone/expiração;
6. moeda/precisão/arredondamento;
7. input/validação/encoding/serialização;
8. API/protocolo/contrato/schema drift;
9. integração externa/rede/DNS/TLS/proxy;
10. authn/authz/RBAC/IDOR/tenant isolation;
11. segurança/abuso/injeção/supply chain;
12. privacidade/LGPD/secrets/logs;
13. UI/navegação/responsividade/browser/device;
14. UX/acessibilidade/prevenção de erro;
15. runtime/exceções/5xx/pageerror/console/requestfailed;
16. performance/capacidade/memória/resource leak/deadlock;
17. filas/workers/schedulers/webhooks/cron;
18. cache/storage/filesystem/disco;
19. observabilidade/health/alerta/falso-verde;
20. CI/CD/build/deploy/config drift/feature flags;
21. backup/restore/rollback/disaster recovery;
22. dependências/licenças/versionamento;
23. quota/rate limit/custo/saturação;
24. efeito externo/reconciliação/compensação;
25. legado/duplicidade/hotfix/processo concorrente;
26. dados órfãos/ghost/stale/unreachable;
27. falha silenciosa/ausência de evento/ausência de produção;
28. teste defeituoso/flaky/mock excessivo;
29. operação manual/runbook/permissão/owner;
30. compliance/regra legal/contratual aplicável.

## 15. AUDIT_UNKNOWN_UNKNOWNS_V1 — a lista nunca é suficiente
A taxonomia é piso, não teto. Reserve uma rodada adversarial exploratória sem roteiro fechado. Use conforme apropriado:
- fuzzing/property-based/mutation testing;
- fault injection/chaos controlado;
- inputs aleatórios e sequências inesperadas;
- navegação e operações fora da ordem esperada;
- replay de dados reais anonimizados;
- comparação diferencial/metamórfica;
- busca por anomalias, outliers e distribuição inesperada;
- inspeção de espaço negativo: o que deveria acontecer e não aconteceu;
- revisão contraditória por outro agente/ferramenta quando útil.
Qualquer nova classe encontrada deve ser incorporada à taxonomia/registro para auditorias futuras.

## 16. AUDIT_CROSS_REPO_PROPAGATION_V1 — regra global não pode divergir
Mudança de política global deve identificar todos os repositórios que carregam a governança e verificar versão/conteúdo. Repositório aplicável desatualizado é achado de governança.
Quando houver automação disponível, a paridade deve ser verificada por hash/marker em CI.

## 17. AUDIT_EVIDENCE_ARTIFACT_V1 — pacote reproduzível
Auditoria formal deve produzir ou atualizar evidência estruturada contendo, conforme aplicável:
- SHA/build/release/ambiente/timestamp;
- mapa de impacto;
- matriz de taxonomia e negativos;
- entidades/IDs de teste não sensíveis;
- comandos/fluxos reproduzíveis;
- resultados antes/depois;
- contagens/reconciliações;
- traces/log refs/screenshots;
- achados/correções;
- risco residual e dívida de evidência.
O pacote deve ser imutável ou versionado e não pode conter secrets.

## 18. AUDIT_SELF_TEST_V1 — testar a própria auditoria
A auditoria deve provar periodicamente que seus gates rejeitam cenários propositalmente defeituosos. Siga `docs/quality/AUDIT_SELF_TEST_V1.md`.
Um mecanismo de auditoria que nunca foi testado contra falhas conhecidas não pode ser tratado como detector confiável.

## 19. AUDIT_JOURNEY_INVENTORY_V1 — superfície e controles completos
Descubra automaticamente quando viável rotas, controles, formulários, ações, estados, roles, tenants, feature flags e caminhos legados. Compare superfície descoberta × inventário declarado × testes existentes. `UNMAPPED_SURFACE` ou controle/jornada material `UNTESTED` bloqueia `APTO`.

## 20. AUDIT_BROWSER_E2E_REAL_V1 — certificação pela experiência real
Fluxo com UI deve ser executado pelo agente em navegador real, sessão gráfica, mesmo release e ambiente. API/CLI/headless-only/screenshot estático são apoio. Reload/revisita, persistência, console/rede e evidência visual são obrigatórios conforme materialidade.

## 21. AUDIT_CLEAN_ROOM_REALITY_V1 — realidade hostil
Quando material, cubra sessão/cache limpos, auth expirada, deep-link/back/refresh, mobile/desktop, browser alternativo, acessibilidade, concorrência, falha parcial, cold start, tempo e soak/leak.

## 22. AUDIT_ESCAPE_INVALIDATION_V1 — aprendizado permanente
Defeito pós-`APTO` dentro do escopo invalida a certificação anterior, exige causa do falso-negativo, prevenção permanente e nova certificação. Reclassificar como pré-existente/UX/raro não evita a invalidação.

## 23. AUDIT_ABSOLUTE_GATE_V1 — zero lacunas
No modo absoluto, `APTO` exige zero defeito P0–P3, zero `DEFECT`, zero `IMPROVEMENT_REQUIRED`, zero `AUDIT_ESCAPE`, zero superfície/jornada/controle material não validado e zero dívida material de evidência. O veredito vem do certifier determinístico.
## Gate de cobertura universal
`APTO` exige que todas as classes materiais desta regra estejam `COMPROVADO` ou `N/A justificado` com evidência. Classe material `NÃO VALIDADO`, superfície/controle não mapeado, reconciliação quebrada, falha silenciosa, evidência stale, teste falso-verde ou defeito aberto bloqueia `APTO` e reabre o loop de remediação.

**Marker de governança:** `AUDIT_UNIVERSAL_COVERAGE_V1`
