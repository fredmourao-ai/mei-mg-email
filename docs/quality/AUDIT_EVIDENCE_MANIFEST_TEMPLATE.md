# Template — AUDIT_EVIDENCE_ARTIFACT_V1

Use este template por auditoria formal. Não inclua secrets, tokens, credenciais, PII desnecessária ou payloads sensíveis.

## Identidade
- Audit ID:
- Data/hora UTC:
- Repositório:
- Branch:
- Commit SHA:
- Build/digest:
- Release:
- Ambiente:
- Auditor(es)/agente(s):

## Proveniência e freshness
- Evidência corresponde ao mesmo SHA/build: SIM/NÃO
- Evidência corresponde ao mesmo ambiente/configuração material: SIM/NÃO
- Evidência coletada em:
- Evidência reutilizada de auditoria anterior: nenhuma / listar + justificar

## Fingerprint do ambiente
- Schema/migration version:
- Config fingerprint (sem secrets):
- Feature flags fingerprint:
- Provider/API versions:
- Hash do artifact/build:

## Inventário de superfície e jornadas
| Tipo | Descobertos | Materiais | Cobertos | Não mapeados | Não testados |
|---|---:|---:|---:|---:|---:|
| Rotas | | | | | |
| Controles interativos | | | | | |
| Jornadas | | | | | |

## Browser E2E real
| Jornada | Browser/host | Sessão gráfica | Passos UI reais | Reload/revisita | Persistência | Console/rede | Evidência visual | Resultado |
|---|---|---|---|---|---|---|---|---|

## Mapa de impacto
| Mudança | Dependentes | Fluxos | Dados | Integrações | Risco | Evidência necessária | Resultado |
|---|---|---|---|---|---|---|---|

## Taxonomia universal
| Classe | Aplicável? | Teste/evidência | Resultado | Achado |
|---|---|---|---|---|

## Negativos e boundaries
| Fluxo | Caso | Estado/dado | Resultado esperado | Resultado observado | Evidência |
|---|---|---|---|---|---|

## Reconciliação de dados
| Fluxo | Origem | Processados | Concluídos | Pendentes justificados | Falhas conhecidas | Diferença inexplicada |
|---|---:|---:|---:|---:|---:|---:|

## Órfãos / estados eternos
| Classe | Consulta/detector | Quantidade | Owner | Prazo/condição | Recuperação |
|---|---|---:|---|---|---|

## Falhas silenciosas
| Fluxo | Sinal aparente | Pós-condição real | Detector independente | Resultado |
|---|---|---|---|---|

## Baseline
| Métrica | Baseline | Release auditado | Variação | Limite/justificativa | Resultado |
|---|---:|---:|---:|---|---|

## Efeitos externos
| Ação | Idempotência | Aceite | Efeito confirmado | Reconciliação | Compensação/recovery |
|---|---|---|---|---|---|

## Observabilidade
| Falha testada | Detector | Alerta/log | Diagnóstico | Recovery | Evidência |
|---|---|---|---|---|---|

## Self-test dos gates
| Cenário injetado | Gate esperado | Resultado observado | PASS/FAIL |
|---|---|---|---|

## Achados e remediação
| ID | P | Natureza | SAFE/REVIEW/MIGRATION/DESTRUCTIVE | Causa raiz | Correção | Regressão | Reauditoria |
|---|---|---|---|---|---|---|---|

## Unknown unknowns
- Técnicas exploratórias usadas:
- Novas classes encontradas:
- Classes promovidas à governança:

## Contraditório independente
- Revisor distinto:
- Findings novos:
- Reauditoria concluída:

## Loop de remediação
- Bloqueadores encontrados:
- Bloqueadores corrigidos:
- Bloqueadores executáveis restantes:
- Bloqueios externos reais:
- Gate enfraquecido para obter verde: NÃO

## Integridade de evidência
| Artifact | Tipo | SHA-256 | SHA/release/ambiente | Proveniência |
|---|---|---|---|---|

## Veredito determinístico
- Manifesto JSON: `AUDIT_CERTIFICATION_MANIFEST_V1`
- Certifier: `scripts/certify-audit-manifest.py`
- Saída obrigatória: `AUDIT_VERDICT=APTO` ou `BLOCKED_EXTERNAL`
- Status escrito pelo agente sem certifier: INVÁLIDO
- Confiança:
- Risco residual:
- Dívida de evidência:
- P0:
- P1:
- P2 críticos:
- IMPROVEMENT_REQUIRED críticos:
- AUDIT_ESCAPE pendentes:
