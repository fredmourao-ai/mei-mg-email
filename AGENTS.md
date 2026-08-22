# Regras obrigatorias para agentes

Este repositorio opera envio de primeiro contato em lote. Agentes, automacoes, PR-healers e scripts autonomos NAO podem alterar a politica de elegibilidade sem aprovacao explicita do usuario.

## Politica atual de exclusao
Nao entram na fila ou no envio apenas:
- empresa com situacao cadastral diferente de ATIVA;
- email contendo a palavra `contabil`;
- email compartilhado por mais de 2 cadastros;
- destinatario/CNPJ ja enviado ou ja enfileirado.

MG e apenas prioridade de ordenacao, nunca filtro de elegibilidade.
## Campos e gates proibidos no fluxo operacional
Nao reintroduzir `marketing_autorizado*`, `mei_verificado*`, `tipo_regime`, `vw_empresas_elegiveis`, `filter_not_mei`, `insert_filter_gate` nem filtro `uf='MG'`.

Nao criar nova view, trigger, migration, guard, gate ou supervisor que reproduza essas regras sob outro nome.

## Protecao obrigatoria
Antes de commit, push, merge, deploy ou restart execute:
`python3 scripts/repo_policy_guard.py`

Se o guard falhar, NAO contorne, NAO edite a lista de proibicoes e NAO force o servico a iniciar. Corrija a regressao.
## Regras de alteracao
- Nao executar `git reset --hard`, checkout destrutivo ou `git pull` que sobrescreva mudancas locais de producao sem revisar diff e rodar o guard.
- Nao religar agentes autonomos durante manutencao do repositorio.
- Nao remover opt-out ou suppressions tecnicas sem revisao especifica.
- Nao alterar a meta de fila 14.800-15.000 sem aprovacao explicita.
- Preserve anti-reenvio e idempotencia do Graph.

O arquivo `AGENTS.md` e parte da politica do repositorio e deve ser lido antes de qualquer alteracao automatizada.
