# Disparo Contabilidade Melo - MEI

## Estado operacional atual

A producao usa **Brevo Transactional Email API** com `EMAIL_PROVIDER=brevo`.
O Microsoft Graph/Exchange foi aposentado do runtime de envio e o NDR Guard legado deve permanecer desabilitado.

Remetente permitido: `atendimento@shopvivaliz.com.br`.
Nome: `Contabilidade Melo`.

HTTP 201 do Brevo significa apenas `submitted`. A entrega so e confirmada quando o reconciliador recebe evento `delivered` para o `messageId` correspondente.

## Limites obrigatorios

- `MAX_ENVIOS_POR_DIA=300`: hard cap absoluto do plano Brevo Free em janela movel local de 24h.
- `META_ENVIOS_POR_DIA=295`: meta operacional com margem.
- O runtime bloqueia configuracao acima de 300 antes do worker iniciar.
- Testes/controlados tambem entram na cota por `mei_email.envios_externos_cota`.
- IDs Brevo sao persistidos como `brevo:<messageId>`.

## Politica de elegibilidade

A fonte de verdade e exclusivamente `AGENTS.md`. Este documento nao redefine filtros. Gates legados aposentados nao podem ser reintroduzidos.

## Deliverability e eventos

`mei-mg-email-brevo-reconciler.service` consulta `/v3/smtp/statistics/events` com timeout, paginação e limites definidos.

- `delivered` atualiza o envio para `delivered`.
- `hardBounce`, `invalid`, `blocked` e `spam` atualizam para `bounce_permanent` e registram suppression tecnica.
- Eventos transitorios e de engagement nao tornam um destinatario reenviavel.
- Eventos terminais ainda sem correspondencia no banco nao sao marcados como vistos; sao tentados novamente no ciclo seguinte.

## Configuracao principal

```ini
EMAIL_PROVIDER=brevo
BREVO_API_KEY=<secret runtime, nunca versionar>
MAIL_FROM=Contabilidade Melo <atendimento@shopvivaliz.com.br>
MAIL_FROM_NAME=Contabilidade Melo
MAX_ENVIOS_POR_DIA=300
META_ENVIOS_POR_DIA=295
RATE_LIMIT_ENVIOS_POR_MINUTO=10
DELIVERABILITY_MAX_ENVIOS_POR_MINUTO=10
MONITOR_BREVO_RECONCILER_UNIT=mei-mg-email-brevo-reconciler.service
```

## Checklist de liberacao

1. manter `/var/lib/mei-mg-email/sender_blocked.pause` presente durante a migracao;
2. validar `scripts/runtime_sender_preflight.py` com provider Brevo, secret presente, remetente correto e 300/295;
3. confirmar monitor, worker, reconciliador Brevo e timer diario instalados;
4. confirmar `mei-mg-email-ndr-guard.service` desabilitado;
5. executar `scripts/enviar_teste_brevo.py` e exigir `BREVO_TEST_DELIVERED=true`;
6. conferir que o teste entrou no ledger de cota;
7. somente depois remover a pausa persistente e reiniciar/recarregar o worker;
8. validar novos envios Brevo-only, cota <=300/24h e ausencia de duplicidade.

## Arquivos principais

- `app/email_provider.py`
- `worker/worker_queue_first.py`
- `scripts/brevo_event_reconciler.py`
- `scripts/enviar_teste_brevo.py`
- `scripts/runtime_sender_preflight.py`
- `scripts/monitor_operacao.py`
- `templates/mei-contabilidade-melo.html`

Segredos nunca devem ser impressos, commitados ou copiados para logs.
