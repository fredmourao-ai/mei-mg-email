# MEI MG Email — recovery memory

Read before changing production, queue, Graph, migrations or infrastructure.

- Production backend is OCI A1 `always-free-arm-1787907847-26`; the retired E2 hosts are not runtime dependencies.
- Never use retired E2 IPs/hostnames in executable configuration.
- Keep exactly one production sender. Canonical worker is `python -m worker.safe_entrypoint_v2` under `mei-mg-email-worker.service`.
- Preserve local work/backups before reset, cleanup or reconciliation. GitHub `main` is canonical for published code.
- Never print/commit Graph credentials, certificates, private keys or tokens.
- Applied Flyway migrations are immutable. During recovery V013/V014/V016/V020 were restored to the checksums already applied in production; do not rewrite applied migration files.
- Fresh 2026-08-31 verification: worker cgroup contained one process; API/worker/replenisher/monitor/NDR/Docker active; zero failed units; `GRAPH_MAIL_READ_OK`; NDR suppression active; queue snapshot `pendente=14790`, `enviando=150`; rolling submitted counts `24h=9499`, `2h=788`, `30m=279`.
- Recent worker batches completed with DB proof and zero failures.
- Do not tune rate/queue or run destructive DB/OCI operations merely to satisfy a monitoring number; diagnose first and preserve safety gates.
- Keep pull-request debt at zero: merge only after green gates or close while preserving evidence.

Cross-project final checkpoint: `Vivaliz-site/site-shopvivaliz` → `docs/operations/recovery/2026-08-31-final-verification.md`.
