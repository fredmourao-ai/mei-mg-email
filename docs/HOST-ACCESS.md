# Acesso canônico aos hosts ShopVivaliz
Fonte central: `Vivaliz-site/site-shopvivaliz/docs/knowledge/host-access.md`. Este arquivo não contém segredos.

## Hosts
- `shopvivaliz-free-a1` — produção web/deploy — `10.0.1.112`.
- `always-free-arm-1787907847-26` — backend/controller/browser — `10.0.1.38`.
- Fred-Win/`LAPTOP-NIG4IFUU` — reverse SSH backend `127.0.0.1:2222` — PASS recente.
- KOCEPSV/`DESKTOP-KOCEPSV` — reverse SSH backend `127.0.0.1:2223` — rota canônica ainda não comprovada operacionalmente; tratar como indisponível até validação fresca.

## Regras
- Navegador de agente somente no backend; nunca em Fred-Win/KOCEPSV.
- Linux via SSH privado/Tailscale e identidade dedicada; SSH público, senha interativa e root público proibidos.
- OCI Bastion/control plane auditável é bootstrap/recovery quando não houver rota privada.
- RustDesk self-hosted é GUI principal; Desktop Commander apenas contingência.
- Windows runtime usa reverse SSH `2222/2223`; relays `5557/5558` apenas bootstrap/recovery.
- Antes de operar, provar `hostname`, `whoami`/`id`, `pwd` e Git.
- Produção `current/` e release ativa são imutáveis.
- Remote Control MCP: controller loopback `127.0.0.1:5580` no backend, nunca público; GitHub não é transporte/queue/heartbeat normal de runtime.
- Nunca registrar valores de chaves, senhas, tokens, cookies, OTP/TOTP ou secrets.
