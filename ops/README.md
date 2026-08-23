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

`mei-mg-email-ndr-guard.service` observa NDRs assincronos da caixa configurada via Microsoft Graph `Mail.Read`. O guard abre `/var/lib/mei-mg-email/sender_blocked.pause` para bloqueios sistemicos, incluindo `AS(42004)`, `5.1.8`, `5.1.90`, `AS:46601` e mensagens de limite de destinatarios em 24 horas.

Antes de habilitar o servico, execute `python scripts/auditar_graph_mail_read.py`. Se o preflight retornar `403 ErrorAccessDenied`, o guard esta cego e deve permanecer desabilitado; nao declare monitoramento de NDR ativo nessa condicao.

Enquanto a leitura autoritativa de NDR nao estiver disponivel, a protecao obrigatoria e o limite local efetivo de 9.000 destinatarios/24h com reserva minima de 1.000 abaixo do teto Exchange de 10.000, alem do gate imediatamente antes de cada submissao Graph.

O worker continua fail-closed quando existir sentinel de pausa. O sentinel nunca deve ser removido automaticamente por um NDR guard, monitor ou rotina de reparo.
