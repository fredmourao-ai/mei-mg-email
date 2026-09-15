# Estado da Auditoria

**Status:** NÃO APTO

Auditoria formal executada segundo `EXTREME_AUDIT_PROTOCOL.md` e o overlay do projeto.

## Última auditoria válida
- Data: 2026-09-15
- Commit/SHA auditado: `03f8a5d231056691ef0a7f9cf7409425dc661375`
- Runtime observado: checkout produtivo em `83d24abd58e234e2a946ff4b46423406173b2e5a`; diferenças até `main` são governança/CI/testes, sem mudança de código runtime
- Veredito: **NÃO APTO PARA CERTIFICAÇÃO**, embora a operação corrente esteja saudável
- Confiança do veredito: alta
- Stop-the-line: recuperação completa do banco ainda não foi provada por restore real

## Evidência executada
No SHA auditado:
- secret scan passou;
- `pip-audit` sem vulnerabilidades conhecidas nas dependências auditadas;
- Bandit high-severity passou;
- compileall passou;
- repo policy guard passou;
- pytest: **230 testes + 5 subtests passaram**;
- GitHub `Email Safety CI` do mesmo SHA passou em push e workflow_dispatch.

Produção observada:
- `mei-mg-email-worker.service`: active/running;
- monitor, queue replenisher, Brevo reconciler e API: active/running;
- API `/health` observada repetidamente com HTTP 200;
- monitor atual `health=ok`, sem hard bounce recente, fila ~14,8k e Brevo reconciler ativo;
- worker corretamente parado por regra de cota ao atingir **300/300 na janela móvel de 24h**;
- banco efetivamente usado possui aproximadamente 15 GB e ~26,7 milhões de registros de empresas (estimativa de catálogo PostgreSQL).

## Achados materiais
### P1 — BACKUP EXISTENTE, RECUPERAÇÃO NÃO COMPROVADA
`shopvivaliz-db-backup.timer` está habilitado. A última execução observada criou dump custom PostgreSQL de ~1,25 GB, validou `pg_restore -l` com 115 entradas, calculou SHA-256, enviou a OCI Object Storage e conferiu tamanho/manifesto remoto.

Entretanto a rotina **não executa restore completo em banco isolado nem valida os dados restaurados**. Pelo critério stop-the-line do protocolo, backup sem restore provado impede `APTO` para dado crítico.

### P2 — proveniência de runtime não é SHA idêntico ao main
O runtime está em `83d24ab...`, enquanto `main` auditado está em `03f8a5d...`. A comparação mostrou apenas mudanças em workflow de CI, governança/documentação de auditoria e teste de continuidade; o código operacional é equivalente. O risco funcional é baixo, mas a proveniência exata permanece uma ressalva de evidência.

### P3 — metadado de serviço desatualizado
A descrição systemd do worker ainda menciona Microsoft Graph App-Only, enquanto a documentação/runtime atual declara Brevo como provedor exclusivo. Não afeta a execução, mas pode induzir diagnóstico operacional incorreto.

## Matriz de cobertura
| Área | Resultado |
| --- | --- |
| testes/segurança/dependências | PASS |
| CI do SHA auditado | PASS |
| worker/monitor/reconciler/API | PASS operacional |
| limite 300/24h | PASS / observado fail-closed |
| fila contínua | PASS operacional |
| reconciliação Brevo | PASS operacional/ativa |
| backup + integridade remota | PASS parcial |
| **restore completo + validação** | **NÃO COMPROVADO** |
| proveniência SHA exato | PARCIAL; runtime equivalente, SHA distinto |

## Risco residual
Moderado. A operação corrente mostra boa saúde e controles corretos de cota/anti-reenvio, mas um desastre de banco ainda não possui prova recente de recuperação integral. Isso impede certificação plena.

## Dívida de evidência / saída do NO-GO
1. restaurar o último dump OCI em PostgreSQL isolado com capacidade adequada;
2. validar schema/migrations, contagens/invariantes críticas e amostra de dados após restore;
3. registrar RPO/RTO medidos;
4. alinhar o checkout/release produtivo ao SHA certificado ou registrar artefato equivalente;
5. atualizar metadado do serviço e reexecutar Gate Final de Completude.

## Regra de validade
Esta auditoria cobre somente o SHA registrado e o runtime observado. Mudança em provider, regras de cota, elegibilidade, fila, banco ou reconciliação exige reauditoria proporcional ao risco.
