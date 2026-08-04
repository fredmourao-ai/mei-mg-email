# Disparo Contabilidade Melo - MEI

## Estado atual

O projeto usa Microsoft Graph com OAuth2 delegado. O SMTP AUTH do tenant permanece desabilitado; isso e intencional e nao e necessario para o fluxo Graph.

## Arquivos

- assets/logo-contabilidade-melo.svg: logo da Contabilidade Melo em SVG.
- templates/mei-contabilidade-melo.html: template HTML da campanha.
- scripts/criar_campanha_contabilidade_melo.py: cria a campanha na API.
- scripts/autorizar_microsoft_graph.py: inicia o login OAuth por codigo de dispositivo.
- scripts/enviar_teste_microsoft_graph.py: envia somente o teste configurado.

## Configuracao local

EMAIL_PROVIDER=microsoft_graph
MICROSOFT_GRAPH_TENANT_ID=ID_DO_TENANT
MICROSOFT_GRAPH_CLIENT_ID=ID_DO_APLICATIVO
MICROSOFT_GRAPH_USER=noreply@ContabilidadeMelo.onmicrosoft.com
MICROSOFT_GRAPH_TOKEN_CACHE=
MAIL_FROM=Contabilidade Melo <noreply@ContabilidadeMelo.onmicrosoft.com>
RATE_LIMIT_ENVIOS_POR_MINUTO=30

O cache de token e salvo fora do repositorio por padrao. Nunca commitar tokens, senhas ou arquivos de cache OAuth.

## Primeiro teste

1. Rode python scripts/autorizar_microsoft_graph.py.
2. Conclua o login Microsoft quando o codigo de dispositivo for exibido.
3. Rode python scripts/enviar_teste_microsoft_graph.py.
4. Confirme a chegada em fredmourao@gmail.com.

A campanha oficial nao deve ser criada nem disparada ate a validacao do teste.

