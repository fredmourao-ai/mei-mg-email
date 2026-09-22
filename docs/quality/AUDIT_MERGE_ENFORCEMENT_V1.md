# AUDIT_MERGE_ENFORCEMENT_V1 — Enforcement de merge e bypass de main

Esta regra fecha a lacuna entre “o gate existe” e “o gate realmente participa do caminho de merge”.

## 1. Governance bridge obrigatório

Todo repositório governado deve possuir `scripts/absolute-audit-governance-validate.sh`.

O bridge executa, no mínimo:

- compilação dos validadores/certifier;
- self-test do certifier;
- self-test da governança;
- paridade global;
- validação dos requisitos locais do projeto.

O `governance-gate` histórico/local deve executar esse bridge **além** dos checks específicos do projeto. O nome/contexto legado não pode ser mantido apontando para um gate mais fraco.

## 2. Main Guard

Todo repositório deve possuir `.github/workflows/absolute-audit-main-guard.yml`, executado em todo push para `main`/ `master`.

O Main Guard deve:

1. executar novamente o bridge V5 absoluto no commit efetivamente publicado em `main`;
2. verificar proveniência do commit por GitHub API;
3. exigir associação a PR realmente mesclado para a branch padrão;
4. produzir artefato de evidência;
5. falhar fechado se a API/proveniência não puder ser comprovada.

Push direto para `main` não vira “APTO” silenciosamente.

## 3. Ruleset / branch protection

Quando o plano e a permissão GitHub permitirem, `governance-gate` e/ou `Absolute Audit Governance` devem ser status checks obrigatórios para `main`, com PR obrigatório e sem bypass.

Quando ruleset/branch protection não estiver disponível no plano ou não puder ser alterado pela credencial do agente:

- isso deve ser registrado como `ENFORCEMENT_PLATFORM_LIMITATION`;
- o bridge + Main Guard continuam obrigatórios;
- o projeto não pode afirmar que o GitHub bloqueia tecnicamente todo push direto; deve afirmar apenas o nível de enforcement realmente comprovado.

## 4. Auto-merge

Qualquer auto-merge/auto-gate deve considerar o `governance-gate` e o gate absoluto como pré-condições. Um script não pode decidir “verde” por contagem parcial de checks.

## 5. Sem enfraquecimento

É proibido:

- renomear/remover o check requerido para contornar branch protection;
- transformar falha do bridge em warning;
- marcar `continue-on-error` no certifier/paridade;
- pular o Main Guard em commits produzidos por bot;
- aceitar push direto como “exceção operacional” sem PR.

**Marker de governança:** `AUDIT_MERGE_ENFORCEMENT_V1`
