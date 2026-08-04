# Dados da Receita Federal

Os arquivos reais ainda não foram fornecidos. Quando chegarem, colocar em
`data/receita/` (já ignorado pelo git — nunca versionar dado real de CNPJ).

## Onde baixar

Portal de Dados Abertos do CNPJ: https://dados.gov.br/dados/conjuntos-dados/cadastro-nacional-da-pessoa-juridica---cnpj
(ou diretamente em https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj/)

Baixar pelo menos:

- `Estabelecimentos*.zip` (vários arquivos numerados, ~1GB cada compactado) — **obrigatório**
- `Empresas*.zip` — opcional, mas necessário pra ter `razao_social` preenchida
- `Simples.zip` — opcional, mas **necessário pra filtrar só MEI** (sem ele, o
  script pega qualquer porte de empresa ativa em MG, não só MEI, e avisa
  isso no log)

Cada arquivo é `.csv` na prática (apesar da extensão às vezes vir diferente),
separado por `;`, **sem cabeçalho**, encoding **latin-1/ISO-8859-1**, layout
fixo por posição de coluna. O layout completo está documentado no próprio
portal ("Layout dos Dados Abertos do CNPJ"). As colunas relevantes usadas
pelo `scripts/ingest_estabelecimentos.py` estão comentadas no próprio script.

## Sobre os arquivos fake em `sample/`

`ESTABELECIMENTOS_fake.csv`, `EMPRESAS_fake.csv` e `SIMPLES_fake.csv` são
dados inventados, no mesmo layout posicional dos arquivos reais, cobrindo
os casos de filtro:

- 4 empresas MG/ATIVA/MEI com e-mail único cada (devem ficar elegíveis)
- 3 CNPJs compartilhando um e-mail (`escritorio3@contafake.com.br`) — no
  limite, NÃO devem ser marcados `provavel_terceiro` (regra é "mais de 3")
- 4 CNPJs compartilhando outro e-mail (`escritorio4@contafake.com.br`) —
  devem ser marcados `provavel_terceiro`
- 1 empresa de SP (deve ser descartada pelo filtro de UF)
- 1 empresa de MG mas com situação BAIXADA (deve ser descartada)
- 1 empresa de MG/ATIVA sem e-mail e/ou não optante do MEI (deve ser
  descartada)

Esses casos são exercitados em `tests/test_ingest.py`.
