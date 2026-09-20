# ARCHITECTURE_DEPLOY_AUDIT_V1 — Arquitetura, Código e Entrega

Esta regra é obrigatória em toda Auditoria Extrema e em mudanças materiais de arquitetura, infraestrutura, CI/CD, deploy, schema, filas, workers, integrações ou limites entre projetos.

## 1. ARCHITECTURE_MAP_V1 — mapa executável
Reconstrua e mantenha:
`usuário/entrada → edge/web → aplicação → serviços → filas/workers → bancos/storage/cache → integrações externas → observabilidade → deploy/rollback`.
Inclua hosts/runners, processos, timers, ownership de dados, contratos e dependências cross-repo. Diagrama/documento desatualizado não prevalece sobre runtime real.

## 2. ARCHITECTURE_FITNESS_FUNCTIONS_V1
Invariantes arquiteturais críticos devem possuir checks automatizados quando tecnicamente viável: isolamento de tenant, direção de dependências, proibição de secrets, ausência de ciclos proibidos, ownership de tabelas/filas, compatibilidade de contratos, limites de workflow/runner, proveniência do release e regras de deploy.

## 3. DEPLOY_CRITICAL_PATH_V1 — medir antes de otimizar
Para cada projeto implantável, meça e registre:
`queue → setup → dependências → testes/gates → build → artifact → transferência → migration → ativação → smoke → reconciliação`.
A auditoria deve identificar o caminho crítico e os passos serializados desnecessários. Melhoria de velocidade nunca pode reduzir cobertura crítica.

## 4. RUNNER_ISOLATION_V1
CI determinístico que não depende do host de produção deve rodar em GitHub-hosted runner ou runner dedicado de CI.
Runner de produção deve ficar reservado para operações que realmente exigem runtime/host/segredos/rede de produção.
Teste longo, lint, compile ou suíte puramente local no runner de deploy é finding de arquitetura quando cria fila ou aumenta lead time.

## 5. BUILD_ONCE_PROMOTE_V1
Quando houver build/dependências empacotáveis, produza um artefato uma vez, associe-o ao SHA/digest e promova o mesmo artefato entre estágios. Evite reinstalar dependências de rede no host de produção durante cutover quando elas podem ser resolvidas previamente.
Artifact deve ser verificável, imutável, sem secrets e com SBOM/checksum quando aplicável.

## 6. DEPENDENCY_CACHE_V1
Use cache determinístico por lockfile/runtime para Composer, npm/pnpm, pip e ferramentas pesadas quando houver ganho material. Cache não pode conter secrets nem substituir verificação de integridade. Meça hit/miss e mantenha fallback limpo.

## 7. CHANGE_AWARE_CI_V1
Classifique impacto por paths/dependências e execute rapidamente os gates afetados; mantenha suíte completa periódica e sempre que risco crítico exigir. Path filtering nunca pode omitir fluxo crítico por desconhecimento de dependência.

## 8. PROVISION_ON_CHANGE_V1
Instalação de pacotes, Apache/Nginx, systemd, certificados, timers, cron, browsers e infraestrutura deve ser idempotente e ocorrer somente quando inputs relevantes mudarem ou quando drift for detectado.
Deploy de código comum não deve repetir provisionamento pesado sem necessidade.

## 9. RESTART_MINIMIZATION_V1
Reinicie/recarregue apenas serviços afetados. Um deploy de frontend/documentação não deve reiniciar workers financeiros, tokens, filas ou integrações sem causa técnica. Registre mapa `path/componente → serviço afetado`.

## 10. MIGRATION_EXPAND_CONTRACT_V1
Schema crítico deve seguir compatibilidade progressiva: expandir → publicar código compatível → migrar/backfill → verificar → contrair em release posterior. Migrations longas ou bloqueantes devem ser separadas do cutover e possuir preflight, backup/restore e rollback operacional.

## 11. CANARY_AND_ROLLBACK_SLO_V1
Defina por projeto:
- como provar canary;
- tempo/condição máximo para detectar release ruim;
- caminho de rollback/roll-forward;
- SLO de restauração;
- quais dados/efeitos externos impedem rollback simples.
Rollback deve ser ensaiado em ambiente seguro equivalente.

## 12. WORKFLOW_SPRAWL_BUDGET_V1
Inventarie workflows ativos, desativados, one-shot e legados. One-shots concluídos e workflows desativados não devem permanecer indefinidamente em `.github/workflows/` quando puderem ser arquivados fora da superfície executável.
Procure jobs equivalentes, schedules sobrepostos, triggers amplos, filas concorrentes e automações que disputam o mesmo runner.

## 13. CROSS_REPO_CONTRACTS_V1
APIs, eventos, arquivos compartilhados, bancos, tokens materializados e contratos entre repositórios devem ter owner, versão e contract tests. Mudança de produtor deve provar compatibilidade com consumidores antes de merge/deploy.

## 14. DATA_OWNERSHIP_V1
Cada tabela, fila, arquivo de estado e efeito externo deve possuir um owner canônico. Escrita concorrente por projetos diferentes é proibida sem protocolo explícito. Integrações devem preferir API/evento/contrato a acesso direto a internals de outro projeto.

## 15. CONFIG_AND_SECRET_ARCHITECTURE_V1
Configuração deve separar código, config não sensível e secrets. `.env` real, credencial, certificado privado, token ou key jamais deve ser versionado. Exemplos devem ser sanitizados. Drift de config entre CI/staging/produção precisa de detector.

## 16. CODE_STRUCTURE_V1
Procure:
- módulos god-object/god-script;
- funções/arquivos excessivamente grandes;
- ciclos de dependência;
- duplicação de regra de negócio;
- versões paralelas `final`, `v2`, `old`, `backup`;
- código morto/feature flag sem owner;
- acesso a infraestrutura espalhado por regra de negócio;
- ausência de boundary entre domínio, adapters e runtime.
Refatoração deve preservar comportamento e ganhar testes antes/depois.

## 17. HOTSPOT_AND_COMPLEXITY_V1
Cruze churn × complexidade × incidentes × criticidade. Hotspot crítico sem testes/owner/observabilidade é `IMPROVEMENT_REQUIRED`. Não priorize apenas tamanho de arquivo.

## 18. DEPLOYMENT_PROVENANCE_V1
Prove `commit → CI → artifact/digest → release → host/process → endpoint/comportamento`. O mesmo SHA deve ser observável no runtime. Cópia manual ou mutable checkout sem proveniência forte é dívida de arquitetura.

## 19. DEPLOYMENT_PERFORMANCE_BUDGET_V1
Cada projeto implantável deve registrar baseline recente de CI/deploy e um budget de regressão. Aumento material de queue/setup/build/deploy deve gerar finding. Otimização deve reduzir lead time sem ocultar checks.

## 20. FAILURE_DOMAIN_AND_BLAST_RADIUS_V1
Mapeie quais componentes podem falhar juntos. Separe runners, workers, bancos, credenciais e deploys quando o acoplamento cria blast radius desnecessário. Uma manutenção de projeto não deve derrubar projeto independente por dependência acidental.

## 21. ARCHITECTURE_DECISION_RECORD_V1
Mudança estrutural material deve registrar decisão, alternativas, trade-offs, rollback e invariantes em ADR/decisão equivalente. Não use ADR para estado operacional temporário.

## 22. ARCHITECTURE_UNKNOWN_UNKNOWNS_V1
Faça rodada contraditória: “qual componente único derruba vários projetos?”, “qual fila não tem backpressure?”, “qual deploy depende de rede externa desnecessariamente?”, “qual secret/config é compartilhado sem contrato?”, “qual job concorre com deploy?”, “qual mudança pequena reinicia demais?”, “qual serviço não pode ser reconstruído do zero?”.

## Gate arquitetural
`APTO` exige que gargalos/riscos materiais identificados estejam corrigidos ou classificados com owner, plano e evidência. Arquitetura que funciona mas possui ponto único crítico, deploy não reproduzível, secret versionado, contrato cross-repo não versionado, runner de produção saturado por CI puro ou rollback não comprovado não pode ser tratada como “sem erro”.

**Marker de governança:** `ARCHITECTURE_DEPLOY_AUDIT_V1`
