# Acesso direto dos agentes as VMs

Instrucao operacional para execucao remota nas VMs Oracle Cloud da ShopVivaliz. Nunca versionar chaves privadas, tokens, senhas ou headers de autenticacao.

## VMs atuais
- `vm1` / `shopvivaliz-free-a1`
- `vm2` / `always-free-arm-1787907847-26`
- OCI: `sa-saopaulo-1`
- Controlador canonico: Fred-Win (`LAPTOP-NIG4IFUU`)
- Perfil OCI obrigatorio: `AGENTS`

## Ordem de acesso
1. Remote Desktop Commander direto pelo nome da VM quando online.
2. SSH somente apos validar host/chave; nunca usar `StrictHostKeyChecking=no`.
3. OCI Compute Instance Run Command como fallback independente de SSH.
4. OCI serial console apenas para recuperacao extrema.

## Uso canonico
No Fred-Win:
```powershell
sv-oci-vm-run vm1 "hostname; id; pwd"
sv-oci-vm-run vm2 "hostname; id; pwd"
```
O helper fica em `C:\Users\FRED\.local\bin\sv-oci-vm-run.ps1`, usa `C:\Users\FRED\.oci\agents\config` e exclusivamente o perfil `AGENTS`.

## Estado validado em 2026-09-06
O Oracle Cloud Agent e o plugin `Compute Instance Run Command` estao ativos nas duas VMs. Testes reais via API OCI terminaram em `SUCCEEDED` com exit code `0` em ambas.

Run Command executa como `ocarun` (UID 999) por padrao. Nao presuma root. Operacoes administrativas exigem canal autorizado com sudo/regra de minimo privilegio.

## Regras
- Nunca copiar a chave privada OCI para as VMs por conveniencia.
- Nunca usar perfil `DEFAULT`; usar somente `AGENTS`.
- Nunca incluir segredo no texto do Run Command.
- `ACCEPTED` nao prova execucao: validar `SUCCEEDED`, stdout e exit code.
- Em falha, conferir status do plugin e `/var/log/oracle-cloud-agent/plugins/runcommand/runcommand.log` antes de alterar configuracao.
