# AUDIT_JOURNEY_INVENTORY_V1 — Inventário exaustivo de jornadas e superfícies

O objetivo desta regra é impedir certificação por amostragem ou por uma lista de testes incompleta.

## Inventário antes do teste

Antes de executar E2E, reconstrua a superfície real do sistema a partir de **múltiplas fontes independentes**:
- rotas/URLs públicas e administrativas;
- menus, links, botões, formulários, dialogs, tabs e ações JS;
- endpoints chamados pela UI;
- operações CRUD e transições de estado;
- roles/permissões/tenants;
- jobs/filas/webhooks acionados pela UI;
- dados novos, legados, migrados, incompletos e estados terminais/intermediários;
- feature flags/configurações materiais;
- histórico de incidentes e `AUDIT_ESCAPE`.

Não confie apenas em documentação ou em uma lista manual.

## Descoberta automática obrigatória quando viável

Para aplicações web, use crawler/browser/DOM instrumentation para enumerar:
- páginas alcançáveis;
- links internos;
- elementos interativos;
- forms/actions;
- controles habilitados por role/estado;
- requests de rede disparadas por interação;
- rotas 404/redirect inesperadas;
- controles sem efeito observável;
- caminhos não alcançáveis pelo menu mas ainda publicados.

Compare `descoberto automaticamente × inventário declarado × testes existentes × rotas/endpoints do código`.

Qualquer item material descoberto e não mapeado é `UNMAPPED_SURFACE` e bloqueia `APTO` até classificação/teste/correção.

## Matriz de jornada

Cada jornada material deve possuir:
`entrada → pré-condições → role/tenant → estado/dado → passos UI → requests → persistência → efeito externo → estado terminal → reload/revisita → evidência → owner`.

Agrupamento só é permitido quando equivalência técnica for provada. “Testei um parecido” não é cobertura.

## Cobertura de controles

Cada botão/link/form/action material deve terminar como:
- `COVERED`: exercitado em jornada real;
- `N/A`: justificativa técnica concreta;
- `DEFECT`: corrigido no loop de remediação.

Controle material `UNTESTED` ou `UNMAPPED` bloqueia `APTO`.

## Espaço negativo

Procure também:
- endpoint sem caller;
- botão sem backend;
- backend sem UI quando deveria haver;
- rota publicada sem navegação;
- estado sem ação de saída;
- ação invisível por erro de permissão/feature flag;
- componente legado ainda acessível;
- fluxo que some do menu mas continua executável.

## Resultado

O pacote de evidência deve conter contagens:
`routes_discovered, interactive_controls_discovered, material_journeys, covered_controls, unmapped_surfaces, untested_material_controls`.

Para `APTO`, `unmapped_surfaces=0` e `untested_material_controls=0`.

**Marker de governança:** `AUDIT_JOURNEY_INVENTORY_V1`
