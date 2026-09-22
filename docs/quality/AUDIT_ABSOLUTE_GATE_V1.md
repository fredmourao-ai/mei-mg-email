# AUDIT_ABSOLUTE_GATE_V1 — Certificação fail-closed máxima

Este é o gate final da Auditoria Extrema V5 absoluta. Ele agrega todas as regras obrigatórias e elimina veredito por opinião do agente.

## Veredito calculado, não declarado

O agente **não pode autoatribuir `APTO`**. Ele produz evidências e um manifesto estruturado; `scripts/certify-audit-manifest.py` calcula o veredito.

Somente a saída `AUDIT_VERDICT=APTO` do certifier, para o mesmo SHA/release/ambiente/escopo, autoriza a palavra `APTO` no relatório final.

Campo ausente, evidência sem hash/proveniência, `NÃO VALIDADO`, defeito aberto, escape pendente ou inconsistência faz o certifier falhar fechado.

## Zero defeito aberto no escopo certificado

Para modo absoluto:
- P0 = 0;
- P1 = 0;
- P2 = 0;
- P3 = 0;
- `DEFECT` aberto = 0;
- `IMPROVEMENT_REQUIRED` aberto = 0;
- `AUDIT_ESCAPE` pendente = 0;
- bloqueador executável = 0;
- superfície/jornada material não mapeada = 0;
- jornada/controle material não testado = 0;
- dívida de evidência material = 0.

P4 `IMPROVEMENT_OPTIONAL` pode permanecer somente se comprovadamente não representar defeito, risco material, prevenção de recorrência, observabilidade, recuperação, integridade, segurança ou confiabilidade operacional.

“Pré-existente” identifica autoria histórica; não isenta correção.

## Escopo explícito e não enganoso

Toda certificação deve nomear exatamente o que cobre. É proibido usar “sistema/site/projeto APTO” se apenas um módulo foi certificado.

Se o pedido for auditoria integral do projeto, o inventário deve abranger todas as superfícies materiais descobertas, inclusive legado ainda executável.

## Invariantes locais obrigatórios

Cada repositório deve possuir `docs/quality/AUDIT_PROJECT_REQUIREMENTS.json`. O certifier carrega esse arquivo e exige todos os invariantes listados; requisito local omitido do manifesto bloqueia `APTO`.

Para requisitos `provider_chat`, cada provider declarado deve estar ativo, produzir resposta não vazia e aparecer visivelmente no mesmo ciclo de UI; todas as fases declaradas também devem completar. Health/configuração não substituem resposta real.

## Auth/login não vira bloqueio cedo

Se o bloqueio alegado for login, OAuth, sessão ou credencial, aplique `AUDIT_AUTH_CREDENTIAL_DISCOVERY_V1`. `BLOCKED_EXTERNAL` é inválido até 100% dos repositórios governados e fontes/sessões/transportes canônicos serem verificados com probes seguros, sem exposição de secrets.
## Independência e contraditório

Jornada crítica exige reauditoria contraditória por revisor/agente distinto. O segundo revisor recebe o escopo, release e evidências necessárias, mas deve tentar falsificar a conclusão e procurar novas classes de falha.

Finding novo volta ao loop de remediação.

## Evidência íntegra

Artefatos materiais devem possuir hash SHA-256 no manifesto. O certifier deve rejeitar referência sem identidade/proveniência. Evidência de outro release/ambiente/config não certifica o atual.

## Invalidação

Mudança material de código, build, schema, config, feature flag, provider/API, release, gate/certifier ou novo `AUDIT_ESCAPE` invalida a certificação afetada e exige evidência nova.

## Estados finais

Durante a execução: `NAO_APTO` é estado intermediário e obriga remediação.

Encerramento só pode ser:
- `APTO`: certifier fail-closed aprovou tudo; ou
- `BLOCKED_EXTERNAL`: existe bloqueio externo real, estreitamente definido e comprovado.

Não existe `APTO COM RESSALVAS` no modo absoluto.

**Marker de governança:** `AUDIT_ABSOLUTE_GATE_V1`
