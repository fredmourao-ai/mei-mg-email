# Registro Global de AUDIT_ESCAPE

Este registro é a memória institucional de defeitos encontrados após uma auditoria que deveriam ter sido detectados pelo escopo declarado.

## Regras
- Não registrar secrets, credenciais, dados pessoais ou conteúdo sensível.
- Cada entrada deve descrever a **classe de falha**, não apenas o caso isolado.
- A entrada só pode ser marcada como encerrada após causa funcional, causa do falso-negativo, correção/prevenção, busca por equivalentes e reauditoria.
- Toda auditoria extrema futura deve revisar as classes abaixo e exercitar as que forem aplicáveis ao projeto/release auditado.
- Quando uma classe for sistêmica, propague a prevenção para os demais repositórios aplicáveis.

## Template

| ID | Data | Projeto/Release | Classe de falha | Causa funcional | Causa do falso-negativo | Superfícies equivalentes | Prevenção adicionada | Projetos aplicáveis | Evidência de reauditoria | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| ESC-YYYY-NNN | YYYY-MM-DD | repo / SHA | classe | causa | por que a auditoria não detectou | rotas/estados/jobs equivalentes | teste/gate/observabilidade/regra | repos | links/artefatos/SHA | OPEN/CLOSED |

## Entradas

Nenhum `AUDIT_ESCAPE` registrado nesta versão inicial.
