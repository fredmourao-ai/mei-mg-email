# Disparo Contabilidade Melo - MEI

## Arquivos adicionados

- `assets/logo-contabilidade-melo.svg`: logo da Contabilidade Melo em formato SVG.
- `templates/mei-contabilidade-melo.html`: template HTML da campanha MEI com logo, oferta e link de descadastro.
- `scripts/criar_campanha_contabilidade_melo.py`: script para criar a campanha na API usando o template pronto.

## Configuracao do remetente Microsoft

No arquivo `.env` local, configure:

```ini
EMAIL_PROVIDER=microsoft
MICROSOFT_SMTP_HOST=smtp.office365.com
MICROSOFT_SMTP_PORT=587
MICROSOFT_SMTP_USER=noreply@ContabilidadeMelo.onmicrosoft.com
MICROSOFT_SMTP_PASS=SUA_SENHA_OU_SENHA_DE_APP
MAIL_FROM=Contabilidade Melo <noreply@ContabilidadeMelo.onmicrosoft.com>
RATE_LIMIT_ENVIOS_POR_MINUTO=30
```

Para Outlook.com, se `smtp.office365.com` falhar, testar:

```ini
MICROSOFT_SMTP_HOST=smtp-mail.outlook.com
```

Nunca commitar `.env` com senha real.

## Como criar a campanha

Com API local rodando:

```powershell
python scripts/criar_campanha_contabilidade_melo.py
```

Isso cria a campanha com filtro `MEI`, lote padrao de 100 contatos e corpo HTML pronto.

## Como iniciar o envio real

1. Conferir que o `.env` esta com `EMAIL_PROVIDER=microsoft` e senha correta.
2. Subir a API.
3. Criar a campanha com o script acima.
4. Rodar o worker:

```powershell
python -m worker.worker
```

Recomendacao: antes do lote oficial, iniciar com poucos contatos de teste e confirmar se o e-mail chega com o logo e sem cair em spam.
