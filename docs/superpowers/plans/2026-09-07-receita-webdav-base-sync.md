# Receita Federal WebDAV Base Sync Implementation Plan

> **For agentic workers:** Use superpowers execution/verification workflows. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the paid Casa dos Dados production base refresh with the official Receita Federal WebDAV monthly snapshot check/import, then release Brevo sending at the explicitly approved 300-email rolling-24h ceiling.

**Architecture:** `scripts/receita_webdav.py` resolves the stable Receita host to the current rotating public Nextcloud share, validates the monthly manifest, downloads one ZIP at a time, streams the CSV directly from the ZIP and batch-upserts eligible companies. The existing `app/queue_manager.py` remains the canonical global shared-email gate (`shared_cnpjs <= 2`) across the complete `mei_email.empresas` table. `scripts/sincronizar_base_diaria.py` remains the audit/orchestration entrypoint. No multi-million-row staging copy is created.

**Tech Stack:** Python 3.12 stdlib (`urllib`, `xml.etree.ElementTree`, `zipfile`, `csv`, `shutil`), psycopg 3, PostgreSQL, pytest, systemd, Brevo Transactional Email API.

**Spec:** `docs/superpowers/specs/2026-09-07-receita-webdav-base-sync-design.md`

## Global Constraints

- Preserve the exact canonical policy in `AGENTS.md`; never reintroduce retired gates or an `uf='MG'` eligibility filter.
- Run `python3 scripts/repo_policy_guard.py` before merge/deploy/restart gates.
- Do not clear opt-outs, suppressions, send history, marketing authorization, third-party classification or anti-replay evidence.
- Base sync never creates campaigns and never starts the worker.
- No paid AI dependency in resident/timer/worker paths.
- Brevo effective target and hard cap are both exactly 300 attributed submissions per rolling 24 hours, as explicitly approved; no configuration may raise the effective cap above 300.
- Never log credentials or rotating public-share tokens.

---

### Task 1: WebDAV discovery, token rotation and manifest contract

**Files:** `scripts/receita_webdav.py`, `tests/test_receita_webdav.py`

- [x] Write RED tests before implementation; initial CI failed because the module did not exist.
- [x] Implement stable-host redirect resolution instead of storing a rotating token.
- [x] Default CNPJ path to `Dados/Cadastros/CNPJ`; explicit `?dir=` still overrides it.
- [x] Parse WebDAV DAV XML and select newest valid `YYYY-MM`.
- [x] Require exactly `Estabelecimentos0.zip` ... `Estabelecimentos9.zip`, all nonzero.
- [x] Validate live against `https://arquivos.receitafederal.gov.br/`: current competence `2026-08`, ten establishment ZIPs.
- [x] Confirm token-rotation RED first: old/frozen token returned 401; tests then required runtime redirect resolution.

---

### Task 2: Disk-safe ZIP streaming and canonical import

**Files:** `scripts/receita_webdav.py`, `tests/test_receita_webdav.py`

- [x] Filter import rows only by current canonical import gates: `ATIVA`, syntactically valid email, no `contabil`; preserve national scope.
- [x] Preserve non-MG rows in tests.
- [x] Before each download require `free >= remote_size + RECEITA_WEBDAV_DISK_RESERVE_BYTES`.
- [x] Download to `.part`, require exact manifest byte count, atomic rename.
- [x] Read one internal CSV directly from `zipfile.ZipFile`; never extract giant CSVs.
- [x] Batch-upsert contact/identity fields only; never update stateful opt-out/send/policy fields.
- [x] Commit completed ZIPs and remove ZIP/`.part` before the next download.
- [x] Keep shared-email multiplicity at its canonical queue boundary: existing `queue_manager.email_counts` counts distinct CNPJs globally and requires `shared_cnpjs <= 2`.
- [x] Avoid PostgreSQL full-snapshot staging because it would unnecessarily duplicate millions of rows on the constrained root disk.

---

### Task 3: Audited daily source orchestration

**Files:** `scripts/sincronizar_base_diaria.py`, `.env.example`, `README.md`, `tests/test_receita_base_sync.py`

- [x] Make `CNPJ_DAILY_SOURCE=receita_webdav` the code/config default.
- [x] Use source name `receita_federal_webdav` and revision `receita:<YYYY-MM>`.
- [x] Same previously successful revision records a new `no_change` without downloading.
- [x] New revision imports and records `success` only after the complete import returns successfully.
- [x] Casa dos Dados and Hugging Face remain explicit fallback/manual modes.
- [x] Document stable host + rotating token resolution and disk-safety settings.
- [ ] Run final full suite, policy guard and `git diff --check` on final branch head.

---

### Task 4: Approved Brevo target 300

**Files:** `app/config.py`, `tests/test_brevo_free_quota.py`, `scripts/materialize_brevo_runtime_secret.py`, `.github/workflows/brevo-runtime-secret.yml`, `.env.example`, current runtime docs.

- [x] TDD RED reproduced: with `MAX=300` and `META=300`, old code returned effective meta 295; 2 tests failed and 1 passed.
- [x] Remove only the obsolete 295 safe-target clamp; retain `brevo_free_hard_cap=300`.
- [x] Prove configured values above 300 still clamp effective max/meta to 300.
- [x] Materializer and secret workflow now expect 300/300.
- [x] Current runtime docs/config now state 300/300.
- [ ] Run final full suite and runtime contract tests on final branch head.

---

### Task 5: PR, CI, review and merge

- [x] PR #111 opened before implementation with TDD RED phase visible.
- [ ] Update PR body with RED/green/live WebDAV evidence and design refinement.
- [ ] Require every applicable CI/check terminal green; inspect/fix any failure rather than bypassing it.
- [ ] Run Superpowers review/verification workflow.
- [ ] Merge PR #111 and verify resulting `main` workflows terminal green.
- [ ] Confirm no relevant open PR/issues or queued/in-progress failing Actions remain.

---

### Task 6: Production deployment and base-sync validation

- [ ] Confirm production tracked checkout clean and `repo_policy_guard` green.
- [ ] Fast-forward production from the authenticated deploy-key remote; no reset/pull/destructive operation.
- [ ] Back up `.env` outside Git.
- [ ] Set `CNPJ_DAILY_SOURCE=receita_webdav`, `RECEITA_WEBDAV_SHARE_URL=https://arquivos.receitafederal.gov.br/`, `RECEITA_WEBDAV_DIRECTORY=Dados/Cadastros/CNPJ`, and `META_ENVIOS_POR_DIA=300`; keep max 300 and preserve secrets/unrelated values.
- [ ] Create `/var/lib/mei-mg-email/receita-cache` owned by runtime user using the documented privileged SSH path.
- [ ] Keep sender pause present and worker inactive during base validation.
- [ ] Run production full tests, policy guard and runtime sender preflight; require effective 300/300.
- [ ] Run one real `scripts/sincronizar_base_diaria.py`; accept only `success` or `no_change` and verify `base_sync_runs` source/revision/details.
- [ ] Monitor disk between every monthly ZIP; never lower the configured safety reserve merely to force progress.

---

### Task 7: Release Brevo and prove exactly 300/24h

- [ ] Audit current rolling quota: queue Brevo submissions + Brevo external ledger; total must be <=300.
- [ ] Validate queue buffer, zero unsafe stale `enviando`, suppressions/dedupe and absence of a sender-block circuit condition.
- [ ] Run runtime sender preflight again at 300/300.
- [ ] Remove only `/var/lib/mei-mg-email/sender_blocked.pause` via documented privileged SSH and restart worker.
- [ ] Verify worker active and singleton advisory lock held.
- [ ] Observe real queue submissions until total attributed rolling 24h reaches **exactly 300**, counting controlled external sends in the same ceiling.
- [ ] Verify no observation exceeds 300.
- [ ] Require real queue rows to have `brevo:` provider IDs and at least one newly released row to reconcile to `delivered`.
- [ ] Confirm no material hard-bounce/sender-block safety trigger occurred.

---

### Task 8: Final operational audit

- [ ] Production SHA equals GitHub `main`; tracked status clean except known protected backup files.
- [ ] Full pytest, repo policy guard and runtime preflight green.
- [ ] Canonical filters in `AGENTS.md` unchanged.
- [ ] Worker/monitor/Brevo reconciler active+enabled; base timer active+enabled; NDR guard inactive+disabled; pause absent.
- [ ] Latest base sync valid on `receita_federal_webdav`.
- [ ] Rolling attributed Brevo total exactly 300 and never >300 during release observation.
- [ ] Real queue delivery evidence exists.
- [ ] GitHub governance clean.
- [ ] Update FRE-74 with final evidence and move it to Done only after every item above is true.
