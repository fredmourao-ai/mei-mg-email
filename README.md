# MEI-MG Email

API + worker para disparo de e-mail em lotes de 100 para MEIs de Minas
Gerais, a partir dos dados abertos de CNPJ da Receita Federal.

**Status:** esqueleto inicial. Banco Postgres local via Docker, API mínima,
worker em modo dry-run (não manda e-mail de verdade ainda). Sem Git
inicializado ainda (proposital, por enquanto). Dado real da Receita ainda
não foi importado — só dados fake pra validar a esteira.

## Por que Postgres (e não SQLite)

SQLite seria mais simples de rodar sem Docker, mas este projeto já nasce
pensando em produção (fila baseada em `SELECT ... FOR UPDATE SKIP LOCKED`,
que SQLite não suporta bem com múltiplos workers, e volume potencialmente
grande — todo MEI ativo de MG). Postgres local via Docker Compose, mesmo
padrão usado no projeto Fala Cidadão, evita esse retrabalho depois.

## Estrutura

```
mei-mg-email/
├── docker-compose.yml       # Postgres 16 + Flyway (migrations automáticas)
├── requirements.txt         # dependências da API/worker
├── requirements-dev.txt     # + pytest
├── .env.example
├── db/
│   ├── init/                # extensões (executado 1x pelo Postgres)
│   └── migrations/          # Flyway: V001 empresas, V002 campanhas/lotes/
│                             # envios/descadastros, V003 trigger de opt-out
│                             # + view de elegibilidade
├── data/
│   ├── README.md            # onde baixar o dado real, layout dos arquivos
│   └── sample/               # CSVs fake no layout real da Receita, p/ teste
├── scripts/
│   └── ingest_estabelecimentos.py   # ingestão CSV -> banco
├── app/                      # API (FastAPI)
│   ├── main.py
│   ├── config.py
│   ├── db.py
│   ├── email_provider.py    # interface EmailProvider + DryRunEmailProvider
│   ├── schemas.py
│   └── routes/
│       ├── campanhas.py     # POST/GET /campanhas, GET /campanhas/{id}/lotes
│       └── descadastro.py   # POST /descadastro
├── worker/
│   └── worker.py            # consome a fila de lotes, dispara (dry-run)
└── tests/
    └── test_ingest.py       # testa os filtros de ingestão contra data/sample
```

## Arquitetura do disparo

```
POST /campanhas
      │
      ▼
seleciona empresas elegíveis (view vw_empresas_elegiveis:
UF=MG, situação ATIVA, opt_out=false, provavel_terceiro=false, tem e-mail)
      │
      ▼
cria campanha + divide em lotes de 100 (tabela `lotes`, status pendente)
      │
      ▼
worker (processo separado, `python -m worker.worker`) faz polling:
  SELECT ... FROM lotes WHERE status='pendente' FOR UPDATE SKIP LOCKED
      │
      ▼
processa cada envio do lote, um por vez, respeitando
RATE_LIMIT_ENVIOS_POR_MINUTO, via EmailProvider.send(...)
      │
      ▼
atualiza envios (enviado/falhou/opt_out) e contadores da campanha
```

A fila é a própria tabela `lotes` do Postgres (`FOR UPDATE SKIP LOCKED`),
não Redis/RabbitMQ — suficiente pro volume esperado e permite rodar mais de
um worker em paralelo sem duas instâncias pegarem o mesmo lote. Migrar pra
uma fila dedicada depois é troca localizada (só `pegar_proximo_lote` no
worker), não redesenho.

## Setup local

```powershell
cd C:\mei-mg-email
copy .env.example .env
# editar .env: trocar POSTGRES_PASSWORD

docker compose up -d
docker compose logs flyway   # confirmar que as migrations rodaram

python -m venv .venv
.\.venv\Scripts\pip install -r requirements-dev.txt

# testar a ingestão com dados fake (sem gravar no banco ainda):
.\.venv\Scripts\python scripts\ingest_estabelecimentos.py --sample --dry-run

# gravar os dados fake de verdade no banco:
.\.venv\Scripts\python scripts\ingest_estabelecimentos.py --sample

# rodar os testes:
.\.venv\Scripts\python -m pytest tests\ -v

# subir a API:
.\.venv\Scripts\uvicorn app.main:app --reload --port 8000

# em outro terminal, subir o worker (dry-run: só loga, não envia nada):
.\.venv\Scripts\python -m worker.worker
```

Nota: o Postgres deste projeto expõe a porta **5433** (não 5432), de
propósito, pra não colidir se o Postgres do Fala Cidadão também estiver
rodando na mesma máquina.

### Testar o fluxo completo (dry-run)

```powershell
curl -X POST http://localhost:8000/campanhas -H "Content-Type: application/json" -d "{
  \"nome\": \"teste dry-run\",
  \"assunto\": \"Novidade para o seu negócio\",
  \"corpo_template\": \"Olá {{razao_social}}! ... Para não receber mais: {{unsubscribe_url}}\",
  \"tamanho_lote\": 100
}"
```

Com o worker rodando, os logs vão mostrar `DRY-RUN: enviaria e-mail
para=...` pra cada empresa elegível — nada é enviado de verdade.

## Regras de negócio já implementadas

- **Filtro de elegibilidade centralizado** na view
  `mei_email.vw_empresas_elegiveis` (UF=MG, situação ATIVA, sem opt-out, sem
  marca de provável terceiro, com e-mail) — a API sempre consulta essa view,
  nunca a tabela `empresas` direto, pra não esquecer nenhum filtro de
  compliance em algum endpoint novo no futuro.
- **"Provável terceiro"**: e-mail que aparece em mais de 3 CNPJs diferentes
  na importação (heurística de contador/escritório compartilhado) é
  marcado, não apagado — fica auditável, só é excluído do envio direto.
- **Opt-out**: `POST /descadastro` registra o pedido; um trigger no banco
  (`V003`) propaga automaticamente pra `empresas.opt_out = true`. O worker
  confirma o opt-out de novo na hora de processar o envio (pode ter
  acontecido entre a criação da campanha e o processamento do lote).
- **Link de descadastro obrigatório**: a API rejeita (`422`) a criação de
  campanha se `corpo_template` não contiver `{{unsubscribe_url}}`.
- **Provedor de e-mail abstraído**: `EmailProvider` (interface) +
  `DryRunEmailProvider` (única implementação, só loga). Trocar por
  SendGrid/SES/SMTP depois é implementar uma classe nova em
  `app/email_provider.py` e apontar `EMAIL_PROVIDER` no `.env`.
- **Reimportação não apaga opt-out**: rodar a ingestão de novo (dado
  atualizado da Receita) faz `UPSERT` por CNPJ, mas nunca sobrescreve
  `opt_out` — uma vez descadastrado, fica descadastrado mesmo que o dado
  de origem mude.

## O que falta

- **Escolher e implementar o provedor de e-mail real** (SendGrid, SES,
  SMTP...) — hoje só existe o dry-run.
- **Importar o dado real da Receita** — ver `data/README.md` pra onde
  baixar. O parser já espera o layout posicional real, só falta o arquivo.
- **Autenticação na API** — hoje qualquer um na rede local pode criar
  campanha. Sem problema pra desenvolvimento, mas precisa de auth antes de
  expor pra fora do localhost.
- **Página de descadastro em HTML** — hoje `/descadastro` é só uma rota de
  API (JSON). O link no e-mail precisa apontar pra uma página de verdade
  (pode ser um formGET simples servido pela própria API depois).
- **Anonimização/retenção** — o Fala Cidadão tem uma regra de anonimizar
  após 90 dias; vale considerar algo parecido aqui também, já que isso é
  dado de contato de pessoa física em bastante caso (MEI = CPF).
- **Rate limit e circuit breaker por domínio de e-mail** — hoje o rate
  limit é global (`RATE_LIMIT_ENVIOS_POR_MINUTO`); provedores de e-mail
  real costumam exigir throttling por domínio destinatário (gmail.com,
  outlook.com...) pra não cair em blocklist.
- **Git** — ainda não inicializado, por pedido explícito. Repositório fica
  pra depois.

## Sobre a Lei Geral de Proteção de Dados (LGPD) e anti-spam

Isso é envio de e-mail em massa a partir de dado público (CNPJ é dado
público, mas e-mail de contato dentro dele é dado pessoal quando MEI = CPF
da própria pessoa). Antes de ligar um provedor de e-mail real e disparar
pra valer, vale revisar com alguém que entenda de LGPD/CDC se a base legal
usada (legítimo interesse, provavelmente) está documentada e se o
tratamento está de acordo — isso não é uma opinião jurídica, só um lembrete
de que a infraestrutura técnica (opt-out, descarte de terceiros, auditoria)
ajuda mas não substitui essa revisão.
