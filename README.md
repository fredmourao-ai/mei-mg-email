# MEI-MG Email

API + worker para disparo de e-mail em lotes de 100 para MEIs de Minas Gerais, a partir dos dados abertos de CNPJ da Receita Federal.

**Status:** Ambiente local configurado com Postgres (Docker), API FastAPI operacional, worker integrado e testado. Controle de priorização por data de abertura e governança de envio único (frequência máxima de 1 e-mail por contato) totalmente implementados e validados por testes de integração. Repositório Git local inicializado e espelhado no GitHub.

---

## 🏗️ Novas Implementações Realizadas

### 1. Governança de Envio Único (Compliance & LGPD)
* **Objetivo:** Garantir que cada MEI receba no máximo um e-mail promocional/campanha e nunca seja re-enviado.
* **Solução:**
  * Adicionadas as colunas `enviado` (boolean, default `false`) e `enviado_em` (timestamptz) na tabela `empresas` (ver [V004__add_enviado_to_empresas.sql](file:///c:/mei-mg-email/db/migrations/V004__add_enviado_to_empresas.sql)).
  * Atualização automática da view de conformidade `vw_empresas_elegiveis` para selecionar apenas empresas onde `enviado = false`.
  * Assim que o worker executa o envio do lote com sucesso, a empresa é marcada na base de dados de contatos (`enviado = true`).
  * Em caso de re-ingestão de dados (atualização a cada 24 horas), o status `enviado` e `opt_out` são mantidos intactos, prevenindo novos envios.

### 2. Fila por Prioridade (Data de Abertura)
* **Objetivo:** Priorizar os novos MEIs ativos no estado de Minas Gerais para assumirem o topo da fila de envio.
* **Solução:**
  * A consulta de seleção de MEIs elegíveis para novas campanhas foi ordenada por `data_abertura DESC` (mais recente primeiro).
  * O particionamento em lotes de tamanho parametrizável (ex: 100) distribui os contatos de modo que os lotes com número menor (ex: Lote 0) contenham os MEIs mais novos, respeitando limites de cota de disparo diário/mensal.

### 3. Redução Drástica de Armazenamento local (Dados Filtrados)
* **Objetivo:** Não necessitar baixar e descompactar os 20GB+ da base nacional da Receita Federal na máquina local.
* **Solução:**
  * Desenvolvido o script [download_cnpj_mg.py](file:///c:/mei-mg-email/scripts/download_cnpj_mg.py). Ele realiza o download dos arquivos compactados zip diretamente dos servidores da Receita Federal, realiza a descompactação e filtragem *on-the-fly* (linha por linha) mantendo apenas os registros de Minas Gerais (MG), salvando no disco apenas arquivos pequenos e leves (~300MB total).

### 4. Simplificação de Dados (Foco Exclusivo em Contatos)
* **Objetivo:** Remover informações desnecessárias de endereço físico/geográfico que não são úteis para contato direto.
* **Solução:**
  * Aplicada a migração [V005__remove_address_and_cnae_columns.sql](file:///c:/mei-mg-email/db/migrations/V005__remove_address_and_cnae_columns.sql) que removeu as colunas `cep`, `municipio`, `cnae` e `cnae_descricao` da tabela `empresas`, mantendo a base ultra leve e estritamente focada em contato.

### 5. API de Atualização de Base Diária
* **Objetivo:** Atualizar a base de dados a cada 24 horas com novos MEIs mantendo os status de envios anteriores.
* **Solução:**
  * Endpoint `POST /empresas/atualizar-base` adicionado à API. Ele faz a leitura dos arquivos de MG gerados pelo downloader, executa o `UPSERT` mantendo intactos os contatos que já receberam e-mail ou solicitaram opt-out.

---

## 📁 Estrutura do Projeto

```
mei-mg-email/
├── docker-compose.yml       # Postgres 16 (Porta 5433) + Flyway (migrations automáticas)
├── requirements.txt         # dependências da API/worker
├── requirements-dev.txt     # + pytest
├── .env.example
├── db/
│   ├── init/                # extensões (executado 1x pelo Postgres)
│   └── migrations/          # Migrações Flyway (V001 a V005)
├── data/
│   ├── README.md            # layout dos arquivos e Mirror da Receita
│   └── sample/              # CSVs fake no layout real da Receita p/ testes
├── scripts/
│   ├── download_cnpj_mg.py  # download sob demanda e filtro de MG on-the-fly
│   └── ingest_estabelecimentos.py   # ingestão de CSVs filtrados -> banco
├── app/                      # API (FastAPI)
│   ├── main.py
│   ├── config.py
│   ├── db.py
│   ├── email_provider.py    # Interface EmailProvider (DryRun e Gmail SMTP)
│   ├── schemas.py
│   └── routes/
│       ├── campanhas.py     # POST/GET /campanhas (criação e lotes)
│       ├── descadastro.py   # POST /descadastro
│       └── empresas.py      # POST /empresas/atualizar-base
├── worker/
│   └── worker.py            # consome a fila de lotes do Postgres, dispara e atualiza status
└── tests/
    ├── test_ingest.py       # testa os filtros de ingestão
    └── test_integration.py  # testa a prioridade por data de abertura e envio único
```

---

## ⚙️ Setup Local e Execução

### 1. Subir Banco de Dados e Migrações (Docker Compose)
Com o Docker Desktop aberto na máquina local, execute:
```powershell
docker compose up -d
```
Confirme se as migrações aplicaram com sucesso:
```powershell
docker compose logs flyway
```

### 2. Criar e Ativar Ambiente Virtual Python
```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements-dev.txt
```

### 3. Baixar e Filtrar os Dados Reais de MG
```powershell
python scripts/download_cnpj_mg.py
```

### 4. Rodar Ingestão dos Dados de MG no Banco
```powershell
python scripts/ingest_estabelecimentos.py \
    --estabelecimentos data/receita/ESTABELECIMENTOS_mg.csv \
    --empresas data/receita/EMPRESAS_mg.csv \
    --simples data/receita/SIMPLES_mg.csv
```

### 5. Executar os Testes Automatizados (pytest)
```powershell
pytest
```

### 6. Iniciar a API e o Worker de Disparo
Subir a API FastAPI (Porta 8000):
```powershell
.\.venv\Scripts\uvicorn app.main:app --reload --port 8000
```
Subir o Worker (em outro terminal):
```powershell
.\.venv\Scripts\python -m worker.worker
```

---

## 🛡️ Provedor de E-mail: Gmail SMTP
O projeto já conta com o `GmailEmailProvider` integrado (ver [email_provider.py](file:///c:/mei-mg-email/app/email_provider.py)). 

Para enviar e-mails de verdade com o Gmail SMTP, configure no seu arquivo `.env`:
```ini
EMAIL_PROVIDER=gmail
GMAIL_ADDRESS=seu_email@gmail.com
GMAIL_APP_PASSWORD=sua_app_password_gerada_no_google
```
*(Lembrando que o Gmail exige o uso de uma **App Password** gerada em https://myaccount.google.com/apppasswords e o 2FA ativo na conta).*
