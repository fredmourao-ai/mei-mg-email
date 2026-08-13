# Operacoes Microsoft 365

## Exchange Online administrativo

O desbloqueio de remetente restrito usa Exchange Online PowerShell com o mesmo App Registration administrativo e certificado X.509 protegido na VM.

Arquivos de credencial esperados na VM:
- `/home/ubuntu/.shopvivaliz/m365/graph-auth.crt`
- `/home/ubuntu/.shopvivaliz/m365/graph-auth.key`

Nunca grave token, chave privada ou senha no GitHub. O procedimento suportado e:

```powershell
pwsh ./scripts/desbloquear_exchange_app_cert.ps1 -ConfirmUnblock
```

O script consulta `Get-BlockedSenderAddress`, executa `Remove-BlockedSenderAddress` somente com confirmacao explicita e exige que o remetente deixe de aparecer em Restricted entities antes de reportar sucesso.

O desbloqueio nao remove automaticamente `/var/lib/mei-mg-email/sender_blocked.pause`. A retomada do worker e uma etapa separada, posterior a propagacao e teste controlado.

## NDR guard

`mei-mg-email-ndr-guard.service` observa NDRs assincronos na caixa Microsoft via Graph `Mail.Read`. Ao detectar `AS(42004)`, `5.1.8` ou equivalente, cria `/var/lib/mei-mg-email/sender_blocked.pause`. O worker continua fail-closed ate remocao operacional deliberada do sentinel.
