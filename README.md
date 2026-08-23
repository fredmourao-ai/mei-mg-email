# MEI-MG Email

Sistema de fila, envio e monitoramento de e-mails para a operação MEI/MG da Contabilidade Melo.

## Produção

- Provedor exclusivo: **Microsoft Graph app-only com certificado X.509**.
- Remetente permitido: `naoresponda@dev.shopvivaliz.com.br`.
- HTTP 202 do Graph é registrado como `submitted`; não representa entrega confirmada.
- SMTP/Gmail/Brevo e autenticação Graph interativa/delegada não são suportados em produção.
- Worker único por advisory lock do PostgreSQL.
- Cota operacional em janela móvel: `META_ENVIOS_POR_DIA=9000`, teto técnico `MAX_ENVIOS_POR_DIA=10000`.
- Modo de recuperação de reputação: `DELIVERABILITY_MAX_ENVIOS_POR_MINUTO=10`.

## Fila contínua

O `queue_replenisher` mantém o buffer de forma independente do worker. Com os defaults atuais:

- `QUEUE_MIN_PENDING=14800`
- `QUEUE_TARGET_PENDING=15000`

Ao atingir o gatilho mínimo, a fila é reposta até o target quando houver destinatários elegíveis. Enfileirar não consome a cota móvel; a trava de 24h é aplicada imediatamente antes de cada submissão.

## Política de importação

A política canônica está em `AGENTS.md`: empresa deve estar ATIVA; e-mail não pode conter `contabil`; e-mail compartilhado por mais de 2 cadastros não entra; destinatário/CNPJ já enviado ou enfileirado não entra. MG é apenas prioridade de ordenação. Gates legados aposentados não podem voltar ao fluxo operacional.

## Atualização diária da base

O timer `mei-mg-email-base-sync.timer` executa diariamente às 03:15 em `America/Sao_Paulo`, com `Persistent=true` e atraso aleatório de até 10 minutos.

A rotina `scripts/sincronizar_base_diaria.py` registra cada execução em `mei_email.base_sync_runs` e não cria campanhas nem inicia o worker.

## Circuit breaker de remetente

Há duas camadas de proteção:

1. o worker abre a pausa ao receber `sender_blocked` de forma síncrona;
2. `mei-mg-email-ndr-guard.service` monitora NDRs assíncronos e abre a mesma pausa ao detectar `AS(42004)`, `5.1.8`, `5.1.90`, `AS:46601` ou equivalente.

O estado persistente fica fora do Git em:

```text
/var/lib/mei-mg-email/sender_blocked.pause
```

O worker não deve ser retomado até o remetente sair de Restricted entities e um teste controlado confirmar propagação.

## Exchange Online administrativo

O App Registration administrativo usa os arquivos protegidos da VM:

```text
/home/ubuntu/.shopvivaliz/m365/graph-auth.crt
/home/ubuntu/.shopvivaliz/m365/graph-auth.key
```

Desbloqueio de Restricted entities:

```powershell
pwsh ./scripts/desbloquear_exchange_app_cert.ps1 -ConfirmUnblock
```

O script consulta `Get-BlockedSenderAddress`, executa `Remove-BlockedSenderAddress` e confirma que o endereço deixou de aparecer na lista. Ele **não remove automaticamente** o sentinel do worker.

## Monitoramento residente

`mei-mg-email-monitor.service` observa:

- profundidade da fila;
- contadores `submitted/enviado` em janelas recentes;
- advisory lock do worker;
- falhas e `sender_blocked` no PostgreSQL;
- estado do timer e idade da sincronização diária.

O NDR guard complementa o monitor para falhas que só aparecem na caixa após o Graph aceitar a submissão.

## Instalação dos serviços na VM

```bash
bash scripts/instalar_monitoramento_vm.sh
```

O instalador cria o estado persistente em `/var/lib/mei-mg-email`, instala/ativa monitor, NDR guard e timer da base, e executa uma sincronização inicial de validação.

## Teste controlado

Após desbloqueio e com o worker ainda pausado:

```bash
python scripts/enviar_teste_microsoft_graph.py
```

O teste usa um destinatário controlado e valida o template atual. Não use esse script para volume.

## Desenvolvimento local

```powershell
docker compose up -d
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements-dev.txt
pytest
```

API local:

```powershell
.\.venv\Scripts\uvicorn app.main:app --reload --port 8000
```

Worker local/dry-run:

```powershell
.\.venv\Scripts\python -m worker.worker
```

## Segurança

- Nunca commite `.env`, senha, token, app password ou chave privada.
- O CI executa `scripts/auditar_segredos_repo.py` e valida sintaxe dos scripts PowerShell.
- Credenciais expostas em commits antigos devem ser rotacionadas; remover o arquivo do `main` não invalida um segredo já publicado no histórico Git.
