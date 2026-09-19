# Operacoes do MEI MG Email

## Runtime atual

A producao usa exclusivamente **Brevo Transactional Email API**. A fonte de verdade de elegibilidade e `AGENTS.md`; este runbook nao redefine filtros.

Servicos esperados:
- `mei-mg-email-worker.service`
- `mei-mg-email-queue-replenisher.service`
- `mei-mg-email-brevo-reconciler.service`
- `mei-mg-email-monitor.service`
- `mei-mg-email-autorepair.timer`

A cota efetiva e fail-closed em **300 submissões por janela móvel de 24h**, incluindo o ledger `mei_email.envios_externos_cota`. A fila pendente e apenas estoque e nao aumenta essa cota ate a submissao real.

O sentinel `/var/lib/mei-mg-email/sender_blocked.pause` continua sendo o circuit breaker canonico. Nenhum monitor ou autorreparo pode remove-lo automaticamente.

O worker tambem abre o circuit breaker de forma fail-closed quando o coorte Brevo das ultimas 24h, com pelo menos 50 envios, excede 2% de `bounce_permanent`. A medicao usa `submitted_at` do proprio envio, nao `updated_at` de suppressions, para evitar falso positivo por reconciliacao tardia.

## Microsoft 365 legado

Microsoft Graph/Exchange Online nao faz parte do runtime de envio. Scripts `auditar_graph_*`, `auditar_dns_microsoft.py`, `desbloquear_exchange_app_cert.ps1` e equivalentes existem apenas para investigacao historica/administrativa e nao autorizam reativar Graph como provider.

`mei-mg-email-ndr-guard.service` deve permanecer **desabilitado**. Nao use limites, reservas, TERRL ou filtros descritos em documentos historicos de Exchange como politica atual.

## Validacao antes de liberar envio

Execute `scripts/runtime_policy_guard.py` e `scripts/runtime_sender_preflight.py`, confirme worker/replenisher/reconciliador/monitor ativos, reconciliacao Brevo sem erro, cota <=300/24h e endpoint publico de descadastro funcional. Segredos nunca devem ser impressos, commitados ou copiados para logs.
