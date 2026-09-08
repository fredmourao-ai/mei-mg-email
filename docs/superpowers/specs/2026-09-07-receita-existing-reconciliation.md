# Receita Existing-Company Reconciliation

## Objective

Harden the official Receita Federal monthly import before the first production snapshot so it does not rewrite millions of unchanged rows and does not leave previously imported CNPJs eligible after Receita changes their cadastral status or contact validity.

## Invariants

- Canonical eligibility in `AGENTS.md` is unchanged.
- MG remains ordering priority only.
- No legacy gate returns.
- Stateful columns such as opt-out, send history, marketing authorization and third-party classification are never rewritten by this reconciliation.
- Production sender remains paused until this change is merged, deployed and validated.

## Design

- Build a bounded Bloom filter of CNPJs already present in `mei_email.empresas` (default 64 MiB).
- Parse all establishment rows, preserving cadastral status even when the row is not currently send-eligible.
- Active rows with valid non-`contabil` e-mail follow the normal insert/upsert path.
- Non-eligible rows are reconciled only when their CNPJ may already exist according to the Bloom filter; false positives are harmless because the SQL is `UPDATE`-only, and Bloom membership has no false negatives for inserted CNPJs.
- Existing inactive CNPJs have their cadastral status refreshed. Active rows whose current Receita e-mail is invalid/`contabil` have the stored e-mail nulled so stale contact data cannot re-enter the queue.
- Upsert uses `WHERE ... IS DISTINCT FROM ...` so unchanged conflicts do not generate row versions/WAL.
- Reconciliation joins with `current.cnpj = incoming.cnpj`, preserving index use.
- Import commits in bounded batches and re-checks disk reserve during processing.

## Verification

TDD RED was observed first: 5 failures / 1 pass for missing classification, WAL guard, reconciliation SQL and Bloom filter. GREEN evidence: 195/195 full pytest, `REPO_POLICY_GUARD_OK`, `compileall`, `git diff --check`, and production PostgreSQL `EXPLAIN` confirming `Index Scan using empresas_pkey` for reconciliation plus `empresas_pkey` conflict arbitration for upsert.
