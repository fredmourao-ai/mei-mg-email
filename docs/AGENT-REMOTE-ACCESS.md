# Acesso remoto dos agentes MEI-MG — topologia vigente 2026-10-29

Este documento é obrigatório para tarefas de VM, email, API, runtime, deploy, logs, navegador ou recuperação. Fonte superior e atualizada: `Vivaliz-site/site-shopvivaliz/docs/knowledge/current-topology-and-access-2026-10-29.md` e `host-access.md` no `main`.

## Hosts e rotas efetivas

- `marina-a1-4c24g` (**OCI ESPOSA**) — produção web/deploy/MySQL/workers. RDC direto está comprovado; escolher o dispositivo pelo nome em `list_devices` e validar identidade e privilégio. SSH/VCN/Tailscale/RDC2 somente com teste independente.
- `always-free-arm-1787907847-26` (**OCI PRINCIPAL**) — backend/controlador MCP/MEI-MG/M365/browser corporativo. ShopVivaliz Remote Control é a rota central para hosts válidos da allowlist. Verificar `hosts_list`/`host_health` antes de executar.
- `shopvivaliz-free-a1` (**excluída**) — **NUNCA** usar `10.0.1.112`, alias SSH, túnel legado, chave associada, retries ou recuperação de runner; não recriar.
- Fred-Win e KOCEPSV são estações auxiliares e não hosts de produção.

## MCP e acesso privado

O MCP central **já não anuncia a origem**, após correção implantada no backend (PR #3391); continua sem expor Marina. O MCP independente da Marina foi codificado em staging read-only, mas seus serviços/tunnel-client estão inativos e a vinculação ao ChatGPT não foi comprovada. Cloudflare admin ativo não valida app. Para Marina, preferir RDC direto atualmente comprovado, com identidade/escopo validado; SSH privado/Tailscale são alternativas somente quando provisionados. OCI Bastion/Run Command/console e GitHub são recuperação/bootstrap formal, não transporte contínuo nem bypass de recusa explícita.

O navegador de agentes e seus perfis Dev/Atendimento permanecem no backend, preservando sessões e MFA, sem cópia de cookies. Não copiar chaves privadas ou secretos entre tenants/hosts.

## Túnel site ↔ MEI-MG e prevenção de regressões

A rota efetiva já foi recuperada por um drop-in privado autorizado `/etc/systemd/system/mei-mg-email-site-tunnel.service.d/50-marina.conf`: serviço ativo no backend, SSH para Marina via Tailscale `100.118.170.46`, host key dedicada e encaminhamento local `127.0.0.1:18010`. A Marina confirmou HTTP **200** em `http://127.0.0.1:18010/health` (snapshot 2026-10-29). **Não confundir esse túnel com o MCP independente OpenAI, ainda não registrado.**

O template versionado foi atualizado para não conter o IP/chave da origem, exigindo override root-owned efetivo; o instalador deve preservar a conexão já funcional e negar ativação sem prova do destino autorizado. Não desabilitar o serviço Marina que já opera, não imprimir chaves/tokens, não reativar `shopvivaliz-free-a1`. O runner dedicado `mei-ci-a1` está instalado mas sem registro local e offline, o que mantém as verificações GitHub aguardando um registro oficial. Não usar o runner principal de e-mails para CI Docker ou backups.

Antes de qualquer mutação, ler os runbooks atuais, identificar host/usuário reais, validar SHA/estado ativo e registrar evidência; correção exige testes e confirmação E2E apropriada. Documentos de setembro são históricos.
