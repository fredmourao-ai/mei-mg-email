# Dados da Receita Federal

Os arquivos reais ainda não foram fornecidos. Quando chegarem, colocar em
`data/receita/` (já ignorado pelo git — nunca versionar dado real de CNPJ).

## Onde baixar

Portal de Dados Abertos do CNPJ: https://dados.gov.br/dados/conjuntos-dados/cadastro-nacional-da-pessoa-juridica---cnpj
(ou diretamente em https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj/)

Baixar pelo menos:

- `Estabelecimentos*.zip` (vários arquivos numerados, ~1GB cada compactado) — **obrigatório**
- `Empresas*.zip` — opcional, mas necessário pra ter `razao_social` preenchida
- `Simples.zip` — opcional; mantido apenas para compatibilidade com chamadas
  antigas, sem dirigir elegibilidade operacional

Cada arquivo é `.csv` na prática (apesar da extensão às vezes vir diferente),
separado por `;`, **sem cabeçalho**, encoding **latin-1/ISO-8859-1**, layout
fixo por posição de coluna. O layout completo está documentado no próprio
portal ("Layout dos Dados Abertos do CNPJ"). As colunas relevantes usadas
pelo `scripts/ingest_estabelecimentos.py` estão comentadas no próprio script.

## Sobre os arquivos fake em `sample/`

`ESTABELECIMENTOS_fake.csv`, `EMPRESAS_fake.csv` e `SIMPLES_fake.csv` são
dados inventados, no mesmo layout posicional dos arquivos reais, cobrindo
os casos de filtro:

- empresas ATIVAS com e-mail único e válido (devem ficar elegíveis,
  independentemente de UF ou MEI)
- 3 CNPJs compartilhando um e-mail (`escritorio3@contafake.com.br`) — no
  limite atual, devem ser descartados na importação (regra é "mais de 2")
- 4 CNPJs compartilhando outro e-mail (`escritorio4@contafake.com.br`) —
  devem ser descartados na importação
- 1 empresa de SP (deve continuar elegível; MG é só prioridade de ordenação)
- 1 empresa com situação BAIXADA (deve ser descartada)
- 1 empresa ATIVA sem e-mail (deve ser descartada)

Esses casos são exercitados em `tests/test_ingest.py`.
