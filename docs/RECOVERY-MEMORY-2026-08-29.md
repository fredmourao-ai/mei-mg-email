# MEI MG Email Recovery Memory — 2026-08-29

## Architecture
Production backend is `always-free-arm-1787907847-26`. The retired E2 hosts must not be treated as dependencies. Recovery is performed on `recovery/two-a1-20260829` and isolated worktrees.

## Binding rules
- Preserve all local/uncommitted backend changes before reconciliation with GitHub `main`.
- Exactly one Microsoft Graph sender may be active in production.
- Do not delete database dumps, migration evidence, config archives or legacy source until independently captured and classified.
- No secrets/private keys/certificates/tokens in Git or logs.
- Validate ingest -> dedupe -> validation -> suppression -> queue -> replenisher -> worker -> Graph send with actual runtime evidence.
- Validate base-sync, timers, monitor and restart/reboot persistence.
- `Mail.Read`/NDR remains an external Microsoft administrative gate if consent is still unavailable; do not retry indefinitely or broaden privileges automatically.
- Service-active status alone is not proof of correctness.

## Recovery sources
- Current backend checkout and PostgreSQL data.
- `/home/ubuntu/oci-a1-migration-20260828` backups and reports.
- GitHub history/workflows.
- Fred Win/Codex history for operational context.

## Cross-project authority
See `Vivaliz-site/site-shopvivaliz` branch `recovery/two-a1-20260829`:
- `docs/operations/TWO-A1-RECOVERY-SPEC-2026-08-29.md`
- `docs/superpowers/plans/2026-08-29-two-a1-recovery-master.md`

Do not declare MEI recovered until the end-to-end audit and sender-uniqueness gate pass.
