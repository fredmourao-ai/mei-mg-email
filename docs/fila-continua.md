# Fila continua MEI/MG

A fila de destinatarios e um buffer operacional independente da cota de envio.

- `META_ENVIOS_POR_DIA=9950` limita somente submissões `submitted/enviado` na janela movel de 24 horas.
- `MAX_ENVIOS_POR_DIA=10000` permanece como teto tecnico local.
- `QUEUE_MIN_PENDING=1000` e o gatilho de reposicao.
- `QUEUE_TARGET_PENDING=5000` e o estoque desejado depois da reposicao.
- O proprio `worker/worker.py` chama `repor_fila_automatica()` antes de buscar o proximo lote.
- Quando a fila cai para 1.000 ou menos, o worker seleciona novos MEIs/MG elegiveis e autorizados e repoe ate 5.000 pendentes.
- Enfileirar nao consome a cota de 24 horas. Antes de cada envio real, o worker consulta novamente `submitted/enviado` das ultimas 24 horas e para em 9.950.
- Ao atingir a cota, os lotes permanecem pendentes; a fila fica pronta para retomar automaticamente conforme a janela movel libera capacidade.

A reposicao usa a mesma advisory lock da criacao de campanhas para evitar concorrencia e a view `vw_empresas_elegiveis`, que preserva situacao ATIVA, opt-out, autorizacao de marketing, verificacao MEI e deduplicacao global por e-mail.

Se nao houver mais registros elegiveis/autorizados, nenhum sistema pode fabricar destinatarios: o worker registra alerta critico para que a base autorizada seja reabastecida. Fora essa condicao de exaustao da base, a fila nao deve chegar a zero.
