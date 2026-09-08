# Receita Existing-Company Reconciliation Plan

**Goal:** Make the first official Receita snapshot safe for the production database and disk before sender release.

- [x] Write failing tests first and observe 5 failures / 1 pass.
- [x] Add bounded existing-CNPJ Bloom filter.
- [x] Preserve inactive cadastral states for update-only reconciliation.
- [x] Null stale e-mail only when Receita says the CNPJ is still ATIVA but current contact is invalid/contains `contabil`.
- [x] Add `IS DISTINCT FROM` conflict filter to avoid unchanged-row WAL amplification.
- [x] Keep stateful opt-out/send/authorization columns untouched.
- [x] Commit in bounded batches and re-check disk reserve.
- [x] Validate production PostgreSQL plans use `empresas_pkey`.
- [x] Run full pytest: 195 passed.
- [x] Run compileall, repo policy guard and diff check.
- [ ] Require all PR checks green.
- [ ] Merge to main and fast-forward production.
- [ ] Re-run full production tests/preflight.
- [ ] Run real Receita base sync to success/no_change while sender remains paused.
- [ ] Audit quota/queue, remove canonical pause, start worker and prove real Brevo delivery to the 300/24h ceiling.
