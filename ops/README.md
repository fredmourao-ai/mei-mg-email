# Operacoes Microsoft 365

O desbloqueio de remetente restrito usa Exchange Online PowerShell, nao Microsoft Graph puro.
Nunca grave tokens neste repositorio. O workflow `Exchange Sender Unblock` aceita tokens apenas por GitHub Actions Secrets e valida a audience antes de conectar.

Secrets reconhecidos, em ordem:
- `EXCHANGE_ADMIN_ACCESS_TOKEN`
- `MICROSOFT_EXCHANGE_ADMIN_TOKEN`
- `MICROSOFT_GRAPH_ADMIN_TOKEN` (somente se o valor for, na pratica, um token emitido para Exchange Online)
- `MICROSOFT_GRAPH_ACCESS_TOKEN` (mesma ressalva acima)

Um access token com audience `https://graph.microsoft.com` sera recusado. Para Exchange Online, o token deve ser emitido para `https://outlook.office365.com/.default` e ter as permissoes/RBAC necessarias ao cmdlet `Remove-BlockedSenderAddress`.
