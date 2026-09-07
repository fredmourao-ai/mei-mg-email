# Receita Federal WebDAV Base Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the paid Casa dos Dados production base refresh with an official Receita Federal WebDAV monthly snapshot check/import, then release Brevo sending at the explicitly approved 300-email rolling-24h ceiling.

**Architecture:** A new focused `scripts/receita_webdav.py` module owns WebDAV discovery, manifest validation, disk-safe one-ZIP-at-a-time download, direct ZIP CSV streaming, PostgreSQL temporary staging, shared-email dedupe, and upsert. `scripts/sincronizar_base_diaria.py` remains the audit/orchestration entrypoint and gains `receita_webdav` as its default source. Sending remains independent, but release happens only after the base sync and Brevo runtime guards are green.

**Tech Stack:** Python 3.12 stdlib (`urllib`, `xml.etree.ElementTree`, `zipfile`, `csv`, `shutil`, `tempfile`), psycopg 3, PostgreSQL, pytest, systemd, Brevo Transactional Email API.

**Spec:** `docs/superpowers/specs/2026-09-07-receita-webdav-base-sync-design.md`

## Global Constraints

- Preserve the exact canonical policy in `AGENTS.md`; do not reintroduce any retired gate or `uf='MG'` eligibility filter.
- Run `python3 scripts/repo_policy_guard.py` before every commit/merge/deploy/restart gate.
- Do not clear opt-outs, suppressions, send history, or anti-replay evidence.
- Base sync must never create campaigns or start the worker.
- No paid AI dependency may be added to any resident/timer/worker path.
- Production sending hard cap is exactly 300 attributed Brevo submissions per rolling 24 hours; the user explicitly approved operating at that ceiling.
- Never log secrets or the Casa dos Dados/Brevo credential values.

---

### Task 1: WebDAV discovery and manifest contract

**Files:**
- Create: `scripts/receita_webdav.py`
- Create: `tests/test_receita_webdav.py`

**Interfaces:**
- Produces: `discover_latest_snapshot(share_url: str, timeout_seconds: int = 30) -> SnapshotManifest`
- Produces: `SnapshotManifest.competence: str`, `files: tuple[RemoteZip, ...]`
- Produces: `RemoteZip.name: str`, `url: str`, `size: int`

- [ ] **Step 1: Write failing tests**

Use deterministic fake WebDAV XML fixtures. Assert that the parser chooses the newest `YYYY-MM`, requires exactly `Estabelecimentos0.zip` through `Estabelecimentos9.zip`, rejects zero/missing/duplicate files, and ignores unrelated ZIPs.

```python
def test_manifest_requires_all_ten_estabelecimentos(monkeypatch):
    monkeypatch.setattr(receita, "_propfind", fake_propfind_missing_7)
    with pytest.raises(RuntimeError, match="Estabelecimentos7.zip"):
        receita.discover_latest_snapshot(SHARE_URL)
```

- [ ] **Step 2: Run focused tests and confirm RED**

Run: `pytest -q tests/test_receita_webdav.py`
Expected: failure because module/interfaces do not exist.

- [ ] **Step 3: Implement minimal discovery**

Parse public Nextcloud share URLs with `urllib.parse`, use `PROPFIND` + basic auth `(token, blank)`, parse DAV XML, choose lexicographically newest valid `YYYY-MM`, and validate exact expected establishment manifest.

- [ ] **Step 4: Run focused tests and policy guard**

Run: `pytest -q tests/test_receita_webdav.py && python3 scripts/repo_policy_guard.py`
Expected: PASS + `REPO_POLICY_GUARD_OK`.

- [ ] **Step 5: Commit**

Commit message: `feat: discover Receita WebDAV snapshots`

---

### Task 2: Disk-safe ZIP streaming and canonical staging

**Files:**
- Modify: `scripts/receita_webdav.py`
- Modify: `tests/test_receita_webdav.py`

**Interfaces:**
- Produces: `import_snapshot(conn, manifest: SnapshotManifest, cache_dir: Path, min_free_bytes: int) -> ImportStats`
- `ImportStats` contains `staged`, `accepted`, `excluded_shared`, `inserted_or_updated`.

- [ ] **Step 1: Write failing ZIP/import tests**

Create tiny in-memory/test ZIPs containing Receita-format semicolon CSV rows. Include: ATIVA valid email, inactive row, `contabil` email, an email shared by 3 CNPJs, a shared email used by 2 CNPJs, and a non-MG company that must remain eligible.

```python
def test_import_preserves_national_scope_and_excludes_shared_gt_two(fake_conn, tmp_path):
    stats = receita.import_snapshot(fake_conn, manifest, tmp_path, min_free_bytes=0)
    assert stats.accepted == 3
    assert "SP" in fake_conn.accepted_ufs
    assert "contabil" not in " ".join(fake_conn.accepted_emails)
```

- [ ] **Step 2: Confirm RED**

Run: `pytest -q tests/test_receita_webdav.py -k import`
Expected: failure because importer is not implemented.

- [ ] **Step 3: Implement sequential download and direct ZIP read**

For each remote ZIP: verify `shutil.disk_usage(cache_dir).free >= remote.size + min_free_bytes`; download to `.part`; require byte count to equal manifest size; atomic rename; open with `zipfile.ZipFile`; require exactly one data member; stream `TextIOWrapper(..., encoding='latin-1')` to `csv.reader`; never extract the uncompressed file.

- [ ] **Step 4: Implement PostgreSQL temp staging**

Within one connection create `TEMP TABLE receita_estabelecimentos_stage (...) ON COMMIT PRESERVE ROWS`. Stage only `ATIVA`, syntactically valid emails without `contabil`. After all ten ZIPs are loaded, upsert only rows whose normalized email appears at most twice in the complete stage:

```sql
with allowed as (
  select lower(email) email
  from receita_estabelecimentos_stage
  group by lower(email)
  having count(distinct cnpj) <= 2
)
insert into mei_email.empresas (...)
select ...
from receita_estabelecimentos_stage s
join allowed a on a.email = lower(s.email)
on conflict (cnpj) do update set
  nome_fantasia = coalesce(excluded.nome_fantasia, mei_email.empresas.nome_fantasia),
  situacao_cadastral = excluded.situacao_cadastral,
  uf = excluded.uf,
  email = excluded.email,
  ddd_1 = coalesce(excluded.ddd_1, mei_email.empresas.ddd_1),
  telefone_1 = coalesce(excluded.telefone_1, mei_email.empresas.telefone_1),
  data_abertura = coalesce(excluded.data_abertura, mei_email.empresas.data_abertura)
```

Do not update stateful opt-out/send/suppression columns.

- [ ] **Step 5: Delete each ZIP after successful streaming and also clean `.part` in failure paths**

Use `try/finally` around each file so transient disk usage is bounded to one ZIP.

- [ ] **Step 6: Run focused tests, full tests and guard**

Run: `pytest -q tests/test_receita_webdav.py && pytest -q && python3 scripts/repo_policy_guard.py`
Expected: all green.

- [ ] **Step 7: Commit**

Commit message: `feat: import Receita snapshot disk safely`

---

### Task 3: Wire Receita into audited daily base sync

**Files:**
- Modify: `scripts/sincronizar_base_diaria.py`
- Modify: `.env.example`
- Modify: `README.md`
- Create: `tests/test_receita_base_sync.py`

**Interfaces:**
- `CNPJ_DAILY_SOURCE=receita_webdav` becomes default.
- `sync_receita_webdav(conn, run_id: int) -> int` records `success` for an imported new competence and `no_change` for an already imported competence.

- [ ] **Step 1: Write RED orchestration tests**

Assert default source name is `receita_federal_webdav`; same latest competence after prior `success/no_change` records a new `no_change` without calling importer; new competence calls importer and records `success`; manifest/import errors record `failed` and return nonzero.

- [ ] **Step 2: Run focused tests and confirm RED**

Run: `pytest -q tests/test_receita_base_sync.py`
Expected: failures for missing source implementation.

- [ ] **Step 3: Implement orchestration**

Use the existing advisory lock and `base_sync_runs` audit pattern. Store revision `receita:<YYYY-MM>` and details including manifest names/sizes and import counts. Keep Casa dos Dados and Hugging Face only as explicit non-default modes.

- [ ] **Step 4: Update docs/config**

Set `.env.example` default to `receita_webdav`; document daily lightweight WebDAV check and monthly bulk import; state that Casa dos Dados is optional/manual and no longer required for production freshness.

- [ ] **Step 5: Run all validation**

Run: `pytest -q && python3 scripts/repo_policy_guard.py && git diff --check`
Expected: all tests green, guard green, no whitespace errors.

- [ ] **Step 6: Commit**

Commit message: `feat: make Receita WebDAV the base sync source`

---

### Task 4: PR, CI, merge and production base-sync validation

**Files:**
- No new source files expected.

- [ ] **Step 1: Open PR from `feat/receita-webdav-base-sync` to `main`**

PR body must include RED evidence, GREEN evidence, canonical-policy statement, disk-safety design, and production validation plan.

- [ ] **Step 2: Require every applicable CI/check to be terminal green**

If any check fails, inspect logs, fix root cause, push correction, and repeat. No bypass/force merge.

- [ ] **Step 3: Merge validated PR and verify resulting `main` workflows**

Confirm no open relevant PR/issues and no queued/in-progress failing workflow remains for the resulting main SHA.

- [ ] **Step 4: Fast-forward production without destructive reset**

Confirm tracked checkout clean, run policy guard, fetch via the existing authenticated deploy-key route, `merge --ff-only`, and verify production SHA equals GitHub `main`.

- [ ] **Step 5: Set protected runtime source**

Change only `CNPJ_DAILY_SOURCE=receita_webdav`; preserve secrets and unrelated runtime values. Keep sender pause present while base-sync is validated.

- [ ] **Step 6: Run production verification**

Run full `pytest -q`, `scripts/repo_policy_guard.py`, `scripts/runtime_sender_preflight.py`, then one real `scripts/sincronizar_base_diaria.py` execution. Accept only `success` or `no_change`; verify latest `base_sync_runs` source/revision/details and timer active+enabled.

---

### Task 5: Release Brevo at 300/24h and prove real operation

**Files:**
- Runtime `.env` only for the user-approved target change; repository docs/config only if tests require documenting the explicit 300 target.

- [ ] **Step 1: Audit current rolling quota before release**

Count queue Brevo submissions (`envios.provider_message_id like 'brevo:%'` + `submitted_at >= now()-24h`) plus `envios_externos_cota` Brevo records. Confirm total <=300 and available capacity is exactly `300-total`.

- [ ] **Step 2: Validate queue safety**

Confirm approximately 14,800-15,000 pending buffer, zero stale `enviando` rows requiring recovery, no sender-blocked circuit breaker records, and canonical dedupe/suppression functions healthy.

- [ ] **Step 3: Set the approved operating target to 300**

Set `META_ENVIOS_POR_DIA=300` while preserving `MAX_ENVIOS_POR_DIA=300`. Run runtime sender preflight again and confirm it reports both values as 300.

- [ ] **Step 4: Remove only the canonical pause sentinel and start worker**

Use administrative SSH per `AGENTS-VM-ACCESS.md` for `/var/lib/mei-mg-email/sender_blocked.pause`; then `systemctl restart mei-mg-email-worker.service`. Verify active unit and held advisory lock.

- [ ] **Step 5: Observe real submissions to the rolling ceiling**

Query production until attributed rolling total reaches 300 without exceeding it. Verify newly processed queue rows have `brevo:` IDs and timestamps after release. External controlled test sends count toward the same 300 ceiling, so the worker must consume only remaining capacity.

- [ ] **Step 6: Prove delivery, not only HTTP submission**

Verify the Brevo reconciler is active and at least one newly released queue row transitions to `delivered` from a real Brevo event. Confirm no material sender-block/hard-bounce safety condition triggered during release.

- [ ] **Step 7: Final operational audit**

Verify worker/monitor/reconciler active+enabled, base timer active+enabled, NDR guard inactive+disabled, pause absent, rolling total exactly 300, rolling total never >300, repository production SHA equals main, tests/guard/preflight green, and GitHub has no relevant PR/Action backlog.

- [ ] **Step 8: Update project task and close only with evidence**

Record final SHAs, base-sync revision/status, quota counts, first real queue Brevo IDs (without recipient PII), delivered evidence, and service states in FRE-74; then move it to Done.