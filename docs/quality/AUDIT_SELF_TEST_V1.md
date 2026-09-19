# AUDIT_SELF_TEST_V1 — Teste do Sistema de Auditoria

Objetivo: provar que a própria Auditoria Extrema falha quando deveria falhar.

## Regra
Sempre que a política/gate de auditoria mudar materialmente, e periodicamente nos repositórios que implementam gates automatizados, execute fixtures ou cenários controlados que contenham defeitos conhecidos. O resultado esperado é a auditoria recusá-los.

## Cenários mínimos
Quando tecnicamente aplicáveis, mantenha casos que representem:
1. P1 conhecido pendente;
2. P2 em fluxo crítico;
3. teste flaky ou skipped indevidamente;
4. HTTP 200 com pós-condição incorreta;
5. worker/job duplicado;
6. entidade órfã ou estado eterno;
7. efeito externo “aceito” porém não reconciliado;
8. evidência de SHA/ambiente diferente;
9. timeout/429/5xx mascarado por fallback;
10. retry que duplica efeito;
11. dado legado incompatível com código atual;
12. alerta/health que permanece verde diante de falha;
13. regressão material de performance/custo;
14. configuração/feature flag divergente;
15. dependência indisponível;
16. ação sem owner/deadline;
17. classe da taxonomia marcada coberta sem evidência;
18. `AUDIT_ESCAPE` ainda não reauditado.

## Teste de sensibilidade
Para cada gate automatizado, pergunte e prove: **qual mutação deliberada faz este gate ficar vermelho?**
Se não houver uma mutação plausível que o gate detecte, ele não conta como evidência forte.

## Teste de especificidade
Também prove que casos válidos não são reprovados sem motivo. Falso positivo recorrente deve ser corrigido; não crie allowlist ampla para silenciá-lo.

## Mutation testing da governança
Quando viável, altere temporariamente uma fixture para remover uma proteção, inverter condição, ignorar exit code, duplicar consumer, alterar boundary ou quebrar reconciliação. O gate deve falhar.

## Resultado
Registre:
`cenário → defeito injetado → gate esperado → resultado observado → evidência → correção do gate se necessário`.

Falha do self-test invalida a confiança no mecanismo correspondente até correção e reexecução.

**Marker de governança:** `AUDIT_SELF_TEST_V1`
