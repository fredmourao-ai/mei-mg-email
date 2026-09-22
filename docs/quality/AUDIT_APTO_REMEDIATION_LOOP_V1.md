# AUDIT_APTO_REMEDIATION_LOOP_V1 — Remediação autônoma até APTO

Auditoria Extrema não termina ao encontrar defeitos. O agente controlador é responsável por **eliminar todo bloqueador executável do veredito APTO**.

## Regra inviolável

Enquanto existir qualquer achado, lacuna de evidência, jornada não validada, erro de runtime, divergência de dados, `AUDIT_ESCAPE`, `IMPROVEMENT_REQUIRED` crítico ou outro requisito material que impeça `APTO`, o agente deve continuar o ciclo de investigação e correção.

É proibido:
- entregar apenas uma lista de problemas corrigíveis;
- classificar problema executável como “pendência para o usuário”;
- parar em PR aberta, patch pronto, checks verdes ou merge;
- rebaixar severidade, remover teste, ampliar allowlist ou enfraquecer gate para obter verde;
- usar “pré-existente” como motivo para aceitar defeito dentro do escopo certificado;
- tratar complexidade, tempo de trabalho, quantidade de arquivos ou número de ciclos como bloqueio externo.

## Loop obrigatório

Para cada bloqueador:
`detectar → reproduzir → causa raiz → classificar risco → corrigir → teste direcionado → busca sistêmica por equivalentes → regressão → deploy quando aplicável → E2E real → persistência/reconciliação → reauditoria contraditória → recertificação`.

Se a correção revelar novo bloqueador, o loop recomeça. Não há limite de iterações baseado em conveniência.

## Modos de correção

- `SAFE`: executar imediatamente.
- `REVIEW`: se a decisão técnica estiver dentro do escopo e das regras já aprovadas, resolver e executar; o rótulo não é estacionamento.
- `MIGRATION`: executar com preflight, backup, compatibilidade expand/contract, verificação, rollback/restore e pós-migração quando tecnicamente autorizado.
- `DESTRUCTIVE`: continua exigindo autorização explícita para o alvo/efeito destrutivo exato. Enquanto não houver essa autorização e não existir alternativa segura, registrar `BLOCKED_EXTERNAL`, nunca `APTO`.

`IMPROVEMENT_REQUIRED` que seja condição de segurança, integridade, observabilidade, recuperação, idempotência, prevenção de recorrência ou confiabilidade da auditoria deve ser implementado antes de `APTO`.

## Bloqueio externo — definição estreita

Só é `BLOCKED_EXTERNAL` quando, após tentativas e alternativas seguras documentadas, a conclusão depende de algo fora da capacidade/autorização técnica disponível, por exemplo:
- credencial realmente revogada/ausente que exija ação do titular;
- CAPTCHA/consentimento/recovery humano sem canal autorizado;
- indisponibilidade comprovada de terceiro sem alternativa;
- decisão comercial/legal não delegada;
- ação destrutiva que exija autorização explícita;
- permissão externa impossível de obter pelo agente.

Um bloqueio deve ter evidência, impacto, ação necessária e critério de desbloqueio. “Não consegui”, “demora”, “é grande”, “precisa de outro agente” ou “teste é manual” não são bloqueios externos.

## Ownership

Delegação não transfere responsabilidade. Se subagente falhar, travar, atingir limite ou não produzir artefatos, o controlador assume ou substitui a execução e continua.

## Estado final permitido

Uma auditoria iniciada para tornar o sistema apto só pode encerrar como:
- `APTO`: todos os gates materiais comprovados e zero bloqueador aberto; ou
- `BLOCKED_EXTERNAL`: bloqueio externo real, provado e incontornável com os acessos/autorização atuais.

`NÃO APTO` é estado intermediário de remediação quando ainda existe correção executável.

**Marker de governança:** `AUDIT_APTO_REMEDIATION_LOOP_V1`
