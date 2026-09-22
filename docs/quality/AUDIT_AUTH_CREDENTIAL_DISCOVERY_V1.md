# AUDIT_AUTH_CREDENTIAL_DISCOVERY_V1 — Descoberta exaustiva antes de bloquear por login

Esta regra é obrigatória antes de classificar autenticação, login, OAuth, sessão ou credencial como `BLOCKED_EXTERNAL`.

## Princípio

“Não encontrei credencial” não é evidência de ausência. O agente deve procurar de forma segura e sistemática em **todos os repositórios governados**, nos perfis/sessões canônicos e nos secret stores/runtime documentados por esses repositórios antes de concluir bloqueio externo.

Nunca imprimir, copiar para chat, commitar, registrar em log ou expor valor de chave, senha, cookie, token, refresh token, OAuth secret ou arquivo de credencial.

## Descoberta obrigatória

1. Identifique exatamente o provider/sistema, método de auth esperado e erro observado.
2. Consulte o manifesto global e enumere todos os repositórios obrigatórios.
3. Em **cada repositório**, procure somente referências seguras:
   - nomes de variáveis de ambiente;
   - nomes de GitHub secrets;
   - caminhos de arquivos privados;
   - perfis de browser/CLI;
   - scripts de instalação/login;
   - unit files/env files;
   - docs/runbooks de OAuth;
   - cadeia de fallback/transporte.
4. Consulte os runtime/secret stores explicitamente referenciados pelos repositórios e acessíveis ao agente, sem exibir o conteúdo:
   - arquivos `.env`/EnvironmentFile protegidos;
   - GitHub Actions secret **names/availability**, nunca valores;
   - OCI Vault/secret manager quando documentado;
   - perfis persistentes de navegador;
   - OAuth/CLI credential stores;
   - systemd user/system environments;
   - connected storage autorizado quando a própria documentação aponta para ele.
5. Verifique primeiro sessão/perfil existente antes de iniciar novo login.
6. Diferencie credencial ausente de token expirado, quota, rate limit, escopo, consentimento, MFA, provider indisponível ou configuração errada.
7. Tente os transportes/fallbacks **explicitamente permitidos** pela política daquele produto.
8. Faça probe real mínimo e seguro para comprovar autenticação; presença/configuração não basta.
9. Se o primeiro mecanismo falhar, continue pelos candidatos válidos antes de bloquear.
10. Só então classifique `BLOCKED_EXTERNAL`, registrando o que foi verificado sem revelar secrets.

## Repositórios governados

A lista canônica vem de `docs/quality/GLOBAL_AUDIT_MANIFEST.json|required_repositories`. A busca deve cobrir 100% da lista vigente, não apenas o repo atual.

## Login via browser

Antes de alegar bloqueio de login:
- reutilize o perfil persistente canônico documentado;
- verifique sessão/cookies por comportamento, sem exportá-los;
- use a VM/browser canônicos;
- tente fluxo de reautenticação permitido;
- se MFA/CAPTCHA/consentimento humano for realmente necessário, prove que não existe sessão válida ou mecanismo autorizado alternativo.

## Evidência

O manifesto deve registrar:
- lista/contagem de repositórios esperados e verificados;
- tipos de fontes verificadas;
- perfis/sessões canônicos avaliados;
- transportes/fallbacks seguros avaliados;
- probe real executado;
- causa final do bloqueio;
- `no_secret_exposure=true`.

Não registre nomes de arquivos privados acompanhados de conteúdo, valores de variáveis, tokens ou cookies.

## Gate

Bloqueio de auth/login sem 100% dos repositórios governados verificados + fontes canônicas de runtime/sessão esgotadas = bloqueio **não comprovado** e a auditoria deve continuar.

**Marker de governança:** `AUDIT_AUTH_CREDENTIAL_DISCOVERY_V1`
