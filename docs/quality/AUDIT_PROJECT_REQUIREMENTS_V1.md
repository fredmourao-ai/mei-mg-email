# AUDIT_PROJECT_REQUIREMENTS_V1 — Invariantes locais machine-readable

Cada repositório governado deve possuir `docs/quality/AUDIT_PROJECT_REQUIREMENTS.json`.

O arquivo lista invariantes do domínio que o certifier global não pode deduzir apenas da taxonomia universal. O agente não pode omitir um requisito local para obter `APTO`.

## Schema mínimo

```json
{
  "schema": "AUDIT_PROJECT_REQUIREMENTS_V1",
  "project": "owner/repo",
  "required_invariants": [
    {
      "id": "EXEMPLO_V1",
      "type": "evidence",
      "description": "invariante material"
    }
  ]
}
```

Tipos suportados:
- `evidence`: exige resultado `COMPROVADO` e artefatos válidos;
- `journey_ids`: além de evidência, exige os IDs de jornadas declarados;
- `provider_chat`: exige cada provider configurado no requisito ativo, resposta não vazia e visível no mesmo ciclo de UI; fases declaradas também devem completar.

O manifesto de certificação deve conter `project_invariants.results`. Cada resultado referencia evidence artifact IDs existentes.

Requisito local ausente, desconhecido, não comprovado ou sem evidência bloqueia `APTO`.

**Marker de governança:** `AUDIT_PROJECT_REQUIREMENTS_V1`
