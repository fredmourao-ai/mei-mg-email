# Fila continua

A fila de destinatarios e um buffer operacional independente da cota de envio.

- `META_ENVIOS_POR_DIA=9950` limita submissões na janela movel de 24 horas.
- `MAX_ENVIOS_POR_DIA=10000` e o teto tecnico local.
- A fila operacional trabalha entre 14.800 e 15.000 registros abertos.
- Cada reposicao adiciona no maximo 200 destinatarios ate retornar ao alvo de 15.000.
- Enfileirar nao consome a cota de envio; a cota e conferida imediatamente antes do Graph.

## Contrato canonico de elegibilidade
Nao entram na fila ou no envio:
- empresa diferente de `ATIVA`;
- email invalido, com opt-out/supressao tecnica, ou contendo `contabil`;
- email compartilhado por mais de 2 cadastros;
- email/CNPJ que ja esteja enfileirado ou possua historico terminal de envio.

`MG` e apenas prioridade de ordenacao. Nunca e filtro de elegibilidade.
Nao usar campos legados de autorizacao/classificacao ou views legadas de elegibilidade como gate operacional.
A politica obrigatoria tambem esta registrada em `AGENTS.md` e protegida por `scripts/repo_policy_guard.py`.
