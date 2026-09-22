# Acesso remoto canônico dos agentes

Este arquivo é leitura obrigatória antes de qualquer tarefa que envolva VM, runtime, navegador, serviço, deploy, logs ou recuperação operacional.

## Hosts canônicos

- `shopvivaliz-free-a1` — produção web — VCN `10.0.1.112`.
- `always-free-arm-1787907847-26` — backend/automação/browser — VCN `10.0.1.38`; Tailscale conhecido `100.66.174.74`.
- `Fred-Win` e `KOCEPSV` são hosts de apoio. Navegador de tarefas ShopVivaliz não deve rodar neles.

## Ordem de acesso

1. **Shell de agentes:** usar SSH privado com o usuário dedicado `shopvivaliz-agent`, somente por VCN/Tailscale. SSH público direto, login root e autenticação por senha continuam proibidos.
2. **Agente cloud sem rota VCN/Tailscale:** não inventar acesso SSH. Usar o control plane auditável do repositório `Vivaliz-site/site-shopvivaliz` e, quando necessário, OCI Bastion. O bootstrap/recuperação canônico vive nesse repositório.
3. **GUI/validação visual:** usar RustDesk self-hosted. O servidor ID/relay está na backend; clientes humanos via Tailscale usam `100.66.174.74`. O campo API pode ficar vazio no servidor OSS. Nunca copiar a chave privada do RustDesk.
4. **Desktop Commander:** contingência apenas. Não é o canal principal e não deve ser usado para tarefas rotineiras.
5. **GitHub Actions/OCI Bastion:** fallback auditável para bootstrap, recuperação e operações quando o agente não possui rota privada direta.

## Navegador

Qualquer navegador, Playwright/Selenium/CDP, MFA, CAPTCHA, consentimento ou validação visual deve usar a VM backend `always-free-arm-1787907847-26`. Não abrir browser em Fred-Win ou KOCEPSV para tarefas ShopVivaliz.

## Segurança e validação

- Nunca imprimir, versionar ou pedir ao usuário chave privada, senha, token ou secret.
- Material de chave do usuário `shopvivaliz-agent` é provisionado pelos fluxos autorizados; não copiar a chave para outro host.
- Antes de agir, validar `hostname`, `whoami`, diretório do repo e estado Git.
- Produção é imutável: no site, não editar a release ativa/`current` diretamente.
- Se o ambiente atual não tiver rota privada, declarar isso e usar o fallback autorizado em vez de concluir que a VM está offline.

## Fonte canônica

A implementação e documentação operacional de referência ficam em:
- `Vivaliz-site/site-shopvivaliz/docs/knowledge/host-access.md`
- `Vivaliz-site/site-shopvivaliz/docs/knowledge/agent-rules.md`
- `Vivaliz-site/site-shopvivaliz/docs/REMOTE-ACCESS-GITHUB.md`

Quando houver divergência, a versão mais recente desses arquivos no `main` de `site-shopvivaliz` prevalece.
