# Acesso direto dos agentes as VMs

Instrucao operacional obrigatoria para agentes que precisem executar comandos nas VMs Oracle Cloud da ShopVivaliz. Nunca versionar, imprimir ou copiar para logs/prompts chaves privadas, tokens, senhas, headers de autenticacao ou conteudo de `security_token_file`.

## VMs atuais

| Alias | Instancia OCI | SSH no Fred-Win | IP publico observado em 2026-09-06 |
| --- | --- | --- | --- |
| `vm1` | `shopvivaliz-free-a1` | `shopvivaliz-a1-site-raw` | `163.176.103.253` |
| `vm2` | `always-free-arm-1787907847-26` | `shopvivaliz-a1-backend-raw` | `144.22.157.209` |

- Regiao OCI: `sa-saopaulo-1`.
- Controlador canonico: Fred-Win (`LAPTOP-NIG4IFUU`).
- Perfil OCI obrigatorio: `AGENTS`.
- Config OCI protegida: `C:\Users\FRED\.oci\agents\config`.
- Helper OCI: `C:\Users\FRED\.local\bin\sv-oci-vm-run.ps1`.
- Executavel SSH canonico no Fred-Win: `C:\Program Files\Git\usr\bin\ssh.exe`.
- Os IPs acima sao informativos; nomes/OCI sao a fonte de verdade caso o IP mude.

## Ordem obrigatoria de acesso

1. **Remote Desktop Commander** diretamente pelo `device_name`, quando online, para operacao comum sem privilegio elevado.
2. **SSH administrativo pelo Fred-Win**, usando o SSH do Git e os aliases ja cadastrados, quando a tarefa exigir `sudo`/root.
3. **OCI Compute Instance Run Command**, via perfil `AGENTS`, como shell de fallback independente de SSH e de porta de entrada.
4. **OCI serial console** somente como ultimo recurso de recuperacao quando acesso privilegiado e SSH estiverem indisponiveis.

Nao enfraquecer os bloqueios de `sudo`/`NoNewPrivileges` do Remote Desktop Commander para conseguir root.

## Shell direto via token/API OCI

Preferir o helper validado. Ele cria o `Instance Agent Command`, aguarda estado terminal, imprime stdout e devolve o exit code remoto:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\FRED\.local\bin\sv-oci-vm-run.ps1 vm1 "hostname; id -un; pwd"
powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\FRED\.local\bin\sv-oci-vm-run.ps1 vm2 "hostname; id -un; pwd"
```

Quando o atalho estiver no `PATH`, a forma curta tambem e valida:

```powershell
sv-oci-vm-run vm1 "hostname; id -un; pwd"
sv-oci-vm-run vm2 "hostname; id -un; pwd"
```

O helper usa somente `C:\Users\FRED\.oci\agents\config` + perfil `AGENTS`; nunca usar `DEFAULT` como fallback.

### Privilegio do Run Command

- O Run Command executa como `ocarun` (UID 999) nas duas VMs.
- Em validacao real de 2026-09-06, `sudo -n` como `ocarun` exigiu senha nas duas VMs. Portanto **nao presuma root pelo token OCI**.
- Use Run Command para shell/diagnostico que nao exija root. Para operacao administrativa, use o SSH autorizado abaixo ou o console serial de recuperacao.
- `ACCEPTED` significa apenas que o comando foi aceito. Sucesso exige `SUCCEEDED`, stdout coerente e exit code `0`.
- O polling do Oracle Agent usa jitter e pode levar alguns minutos. Nao relance comandos duplicados apenas porque permaneceram em `ACCEPTED` por um ciclo.

## SSH administrativo canonico

No Fred-Win, usar os aliases existentes e **o OpenSSH distribuido com Git**:

```powershell
& 'C:\Program Files\Git\usr\bin\ssh.exe' -o BatchMode=yes shopvivaliz-a1-site-raw 'hostname; id -un; sudo -n id -u'
& 'C:\Program Files\Git\usr\bin\ssh.exe' -o BatchMode=yes shopvivaliz-a1-backend-raw 'hostname; id -un; sudo -n id -u'
```

Validacao real de 2026-09-06: ambos os aliases autenticaram e `sudo -n id -u` retornou `0` com exit code local `0`.

Na sessao automatizada do Fred-Win, `C:\Windows\System32\OpenSSH\ssh.exe` retornou exit `255` sem stderr, enquanto `C:\Program Files\Git\usr\bin\ssh.exe` funcionou. Ate nova validacao, agentes devem preferir o SSH do Git. Nunca usar `StrictHostKeyChecking=no`.

## Remote Desktop Commander

Device names atuais:

- `shopvivaliz-free-a1`
- `always-free-arm-1787907847-26`

O DC e o caminho mais simples para comandos sem root. Seu bloqueio de comandos privilegiados e intencional; nao alterar essa politica como atalho operacional.

## Estado validado em 2026-09-06

- Oracle Cloud Agent e plugin `Compute Instance Run Command`: `RUNNING` nas duas instancias pela API OCI.
- Helper `sv-oci-vm-run vm1`: retornou `HELPER_OK`, `shopvivaliz-free-a1`, `ocarun`, exit code `0`.
- Helper `sv-oci-vm-run vm2`: retornou `HELPER_OK`, `always-free-arm-1787907847-26`, `ocarun`, exit code `0`.
- SSH Git + alias `shopvivaliz-a1-site-raw`: acesso administrativo validado, `sudo -n id -u` = `0`.
- SSH Git + alias `shopvivaliz-a1-backend-raw`: acesso administrativo validado, `sudo -n id -u` = `0`.

## Diagnostico e seguranca

- Validar OCI antes de operar: `oci iam region list --config-file C:\Users\FRED\.oci\agents\config --profile AGENTS`.
- Se Run Command ficar parado, revisar o plugin e `/var/log/oracle-cloud-agent/plugins/runcommand/runcommand.log`.
- Nunca colocar segredo no texto de Run Command. Use mecanismo seguro aprovado para dados sensiveis.
- Nunca copiar a chave privada OCI para as VMs por conveniencia.
- Nunca imprimir a chave SSH privada nem a chave OCI em logs, issues, PRs ou respostas.
- Nao interromper o Oracle Cloud Agent ou o plugin a partir de um Run Command.
- Depois de qualquer comando de mudanca, executar verificacao real independente antes de declarar sucesso.
