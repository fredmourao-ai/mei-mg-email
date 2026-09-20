# Fila continua

A fila de destinatarios e um buffer operacional independente da cota de envio.

- `META_ENVIOS_POR_DIA=300` e a meta operacional atual do Brevo Free.
- `MAX_ENVIOS_POR_DIA=300` e o teto absoluto local em janela movel de 24h.
- A fila operacional trabalha entre 14.800 e 15.000 registros abertos.
- Cada reposicao adiciona no maximo 200 destinatarios ate retornar ao alvo de 15.000.
- Enfileirar nao consome cota; a cota e conferida imediatamente antes de cada submissao ao Brevo.
- Testes/controlados tambem consomem a mesma cota via `mei_email.envios_externos_cota`.

## Contrato canonico de elegibilidade

### Filtros de negocio permitidos
Nao entram na fila ou no envio por regra de negocio apenas:
- empresa diferente de `ATIVA`;
- email contendo `contabil`;
- email compartilhado por mais de 2 cadastros;
- email/CNPJ que ja esteja enfileirado ou possua historico de submissao/envio.

### Protecoes tecnicas obrigatorias
Sem criar novo filtro de segmentacao, o runtime tambem bloqueia de forma fail-closed email ausente/invalido, opt-out, suppression tecnica e divergencia entre o email atual da empresa e o email enfileirado. Essas protecoes existem para consentimento, entregabilidade, integridade e anti-replay.

`MG` e apenas prioridade de ordenacao. Nunca e filtro de elegibilidade.
Nao usar campos legados de autorizacao/classificacao ou views legadas de elegibilidade como gate operacional.
A fonte de verdade e `AGENTS.md`, protegida por `scripts/repo_policy_guard.py` e `scripts/runtime_policy_guard.py`.
