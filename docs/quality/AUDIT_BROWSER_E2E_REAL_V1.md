# AUDIT_BROWSER_E2E_REAL_V1 — E2E real obrigatório no navegador

Esta regra é inseparável da Auditoria Extrema para todo sistema que possua interface web.

## Princípio inviolável

Se uma operação existe na UI, a certificação funcional dessa operação deve ser obtida pelo **fluxo real do usuário no navegador real**, contra o **mesmo SHA/build/release/ambiente** que receberá o veredito.

`curl`, API direta, SQL, chamada interna, fixture, unit/integration test, healthcheck, inspeção de código, screenshot estático e browser apenas headless são evidências auxiliares. Nenhum deles substitui o E2E real pela UI.

## Responsabilidade do agente

O agente controlador deve executar o E2E. Não pode transferir ao usuário cliques, navegação ou screenshots que estejam tecnicamente ao alcance do agente. Evidência humana pode complementar, nunca substituir.

Falta de navegador, sessão, autenticação ou acesso ao ambiente torna a jornada `NÃO VALIDADA` / `BLOCKED_EXTERNAL`; nunca autoriza inferir sucesso.

## Definição de E2E real

Para cada jornada material:
1. abrir a entrada publicada usada pelo usuário;
2. autenticar pela UI quando aplicável;
3. navegar pelas telas reais, sem pular diretamente para endpoints internos;
4. clicar controles reais;
5. preencher e selecionar campos pela UI;
6. submeter pela UI;
7. observar loaders, redirects, mensagens, erros e estados intermediários;
8. comprovar a pós-condição final na UI;
9. recarregar;
10. navegar para fora e retornar;
11. comprovar persistência;
12. quando houver estado durável ou efeito externo, reconciliar por canal independente.

## Browser dirigido por automação

Playwright/Selenium/CDP podem dirigir o browser real. Porém:
- execução **somente headless** não certifica uma jornada visual/operacional quando a sessão gráfica real está disponível;
- mocks/intercepts que substituam backend/provider material invalidam a certificação daquele efeito;
- screenshot sem interação ponta a ponta é evidência visual, não E2E;
- fixtures podem preparar dados, mas não podem saltar a operação que o usuário executaria pela UI.

## Cobertura

Antes de testar, inventarie todas as jornadas materiais. Cada jornada deve terminar em `COMPROVADO`, `N/A justificado` ou `NÃO VALIDADO`.

Não é permitido certificar por amostragem que omita uma classe material de estado, role, tenant, dado legado/novo, feature flag, erro, boundary ou transição.

## Evidência mínima por jornada

Registre:
- SHA/build/release/ambiente/timestamp;
- browser, host/sessão e identidade não sensível da fixture;
- URL inicial/final;
- sequência de ações da UI;
- screenshot/vídeo/trace dos marcos;
- console, pageerror, requestfailed e rede HTTP;
- estado antes/depois;
- reload/revisita;
- persistência;
- reconciliação independente quando aplicável;
- reexecução contraditória.

## Gate fatal

Bloqueiam `APTO`:
- jornada crítica com UI não percorrida no browser real;
- substituição da UI por API/CLI;
- browser em release diferente;
- execução somente local quando o alvo é publicado;
- execução somente headless usada como prova final;
- mutação sem reload/revisita;
- pós-condição não comprovada;
- `5xx`, `pageerror`, `requestfailed`, `console.error` inesperado;
- erro visual, blank state ou fallback silencioso;
- efeito externo não reconciliado;
- usuário executando no lugar do agente;
- evidência sem proveniência.

## Ações irreversíveis

A exigência E2E não autoriza cobrança real nem destruição. Quando o passo terminal for financeiro/irreversível, use sandbox, fixture descartável, modo não financeiro ou limite seguro oficialmente suportado, mantendo o caminho real de UI até esse limite e registrando exatamente o que não foi executado.

## Pós-deploy

E2E anterior ao deploy não certifica produção. Após deploy, repita as jornadas materiais afetadas no release ativo e reconcilie efeitos assíncronos.

**Marker de governança:** `AUDIT_BROWSER_E2E_REAL_V1`
