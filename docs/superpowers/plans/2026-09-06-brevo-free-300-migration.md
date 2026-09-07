# Brevo Free 300 Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the cancelled Microsoft Graph production sender with Brevo Transactional Email, reconcile real delivery outcomes, and enforce a fail-closed 300-submission rolling 24-hour hard cap.

**Architecture:** Brevo submissions are stored as `brevo:<messageId>` so Brevo quota is isolated from historical Graph traffic without a database migration. A deterministic Brevo event reconciler upgrades accepted rows to delivery/bounce outcomes. The existing persistent sender pause remains the cutover gate until a controlled message is truly delivered.

**Tech Stack:** Python 3, urllib, PostgreSQL/psycopg, systemd, pytest, Brevo v3 API, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-06-brevo-free-300-migration-design.md`

## Global Constraints
- Hard cap: 300 Brevo accepted submissions in any rolling 24 hours.
- Operational target: 295/24h; 5-message reserve.
- Queue remains 14,800/15,000.
- Preserve current `AGENTS.md` eligibility exactly; never restore retired gates.
- `submitted` never means delivered.
- Graph is not a production fallback after cutover.
- Run `python scripts/repo_policy_guard.py` before every commit/push/merge/deploy/restart.
- Every commit must be pushed immediately; final state requires merged PR and green post-merge checks.

---

### Task 1: Brevo provider and hard quota configuration

**Files:**
- Modify: `app/email_provider.py`
- Modify: `app/config.py`
- Create: `tests/test_brevo_provider.py`
- Create: `tests/test_brevo_free_quota.py`

**Interfaces:**
- Produces: `BrevoEmailProvider`, `brevo_storage_message_id(raw_id: str) -> str`, effective `settings.max_envios_por_dia <= 300`, target <=295.
- Consumes: existing recipient validation and `SendResult`.
- [ ] **Step 1: Write provider/config tests that fail on the Graph-only implementation**

```python

def test_brevo_storage_id_is_provider_attributed():
    assert brevo_storage_message_id("<abc@example>") == "brevo:<abc@example>"


def test_brevo_free_defaults_never_exceed_300(monkeypatch):
    monkeypatch.setenv("MAX_ENVIOS_POR_DIA", "10000")
    monkeypatch.setenv("META_ENVIOS_POR_DIA", "9950")
    settings = reload_settings()
    assert settings.max_envios_por_dia == 300
    assert settings.meta_envios_por_dia == 295
```

The provider test must monkeypatch `urlopen`, assert `POST /v3/smtp/email`, `api-key` presence without logging its value, fixed sender/reply-to, HTML/text payload, and require HTTP 201 plus non-empty `messageId` before returning `submitted`.

- [ ] **Step 2: Run focused tests and verify RED**

```text
py -3 -m pytest tests/test_brevo_provider.py tests/test_brevo_free_quota.py -q
```
Expected: failure because Brevo is disabled and Exchange quota logic is active.

- [ ] **Step 3: Implement the minimal Brevo provider and quota clamp**

`get_email_provider("brevo")` and `brevo_api` must return `BrevoEmailProvider`; production aliases for Microsoft/Graph remain disabled by the factory. Keep the legacy Graph class only for historical/admin code until dependent scripts are retired.

- [ ] **Step 4: Verify GREEN, policy guard, then publish immediately**

```text
py -3 -m pytest tests/test_brevo_provider.py tests/test_brevo_free_quota.py -q
py -3 scripts/repo_policy_guard.py
git add app tests
git commit -m "feat: add Brevo free sender and hard cap"
git push origin feat/brevo-free-300
```

### Task 2: Provider-specific rolling quota and provider-independent replay guard

**Files:**
- Modify: `worker/worker_queue_first.py`
- Modify: `worker/worker.py`
- Create: `tests/test_brevo_worker_contract.py`

**Interfaces:**
- Produces: rolling count based only on `brevo:%` accepted submissions and Brevo external ledger entries.
- Preserves: anti-replay across Graph, Brevo and historical terminal outcomes.
- [ ] **Step 1: Write RED tests for quota attribution and replay**

```python

def test_quota_counts_only_brevo_submission_evidence():
    source = WORKER_SOURCE
    assert "provider_message_id like 'brevo:%'" in source.casefold()
    assert "submitted_at" in source


def test_replay_guard_does_not_depend_on_current_terminal_status():
    source = WORKER_SOURCE.casefold()
    assert "provider_message_id is not null" in source
    assert "submitted_at is not null" in source
```

Also assert worker startup rejects an effective cap above 300 and provider-neutral dispatch messages do not claim Graph/Exchange.

- [ ] **Step 2: Run focused tests and verify RED**

```text
py -3 -m pytest tests/test_brevo_worker_contract.py -q
```

- [ ] **Step 3: Implement quota/replay semantics**
Use `provider_message_id LIKE 'brevo:%' AND submitted_at >= statement_timestamp()-interval '24 hours'` for queued Brevo quota, and Brevo-attributed external ledger rows for out-of-band quota. Use durable prior submission evidence for global replay protection regardless of final delivery status.

- [ ] **Step 4: Run focused + regression tests, guard, commit and push**

```text
py -3 -m pytest tests/test_brevo_worker_contract.py tests/test_dispatch_replay_guard.py tests/test_first_send_policy.py -q
py -3 scripts/repo_policy_guard.py
git add worker tests
git commit -m "fix: isolate Brevo quota and preserve replay guard"
git push origin feat/brevo-free-300
```

### Task 3: Brevo delivery-event reconciler

**Files:**
- Create: `scripts/brevo_event_reconciler.py`
- Create: `deploy/systemd/mei-mg-email-brevo-reconciler.service`
- Modify: `scripts/monitor_operacao.py`
- Modify: `scripts/instalar_monitoramento_vm.sh`
- Create: `tests/test_brevo_event_reconciler.py`
- Modify: `tests/test_monitor_operacao.py`
- Modify: `tests/test_service_continuity_guards.py`

**Interfaces:**
- Consumes: Brevo `/v3/smtp/statistics/events` and `brevo:<messageId>` storage IDs.
- Produces: idempotent `delivered`/`bounce_permanent` evidence and durable hard-bounce suppression.
- [ ] **Step 1: Write RED event mapping/idempotency tests**

```python

def test_delivered_event_maps_to_delivered():
    assert classify_event({"event": "delivered"}).status == "delivered"


def test_permanent_brevo_failures_create_hard_bounce():
    for event in ("hardBounce", "invalid", "blocked", "spam"):
        outcome = classify_event({"event": event, "reason": "x"})
        assert outcome.status == "bounce_permanent"
        assert outcome.suppress is True
```

Mock DB/API boundaries to prove duplicate events are harmless, transient events do not make a message replayable, and stored IDs are matched as `brevo:<raw-id>`.

- [ ] **Step 2: Run focused tests and verify RED**

```text
py -3 -m pytest tests/test_brevo_event_reconciler.py tests/test_monitor_operacao.py -q
```

- [ ] **Step 3: Implement reconciler and operational wiring**
Poll Brevo with bounded request timeout and page limit, persist a bounded seen-event state in `/var/lib/mei-mg-email/brevo_event_state.json`, update delivery/bounce evidence transactionally, and call `register_operational_suppression` only for permanent outcomes. Installer must enable the Brevo reconciler and disable the legacy Exchange NDR guard.

- [ ] **Step 4: Verify, guard, commit and push**

```text
py -3 -m pytest tests/test_brevo_event_reconciler.py tests/test_monitor_operacao.py tests/test_service_continuity_guards.py -q
py -3 scripts/repo_policy_guard.py
git add scripts deploy tests
git commit -m "feat: reconcile Brevo delivery events"
git push origin feat/brevo-free-300
```

### Task 4: Runtime fail-closed preflight, controlled delivery proof and docs

**Files:**
- Modify: `scripts/runtime_sender_preflight.py`
- Create: `scripts/enviar_teste_brevo.py`
- Modify: `deploy/systemd/mei-mg-email-worker.service`
- Modify: `README.md`
- Modify: `AGENTS.md` only to replace Graph-specific replay wording with provider-neutral replay wording; canonical eligibility text must remain byte-for-byte semantically identical.
- Create: `tests/test_brevo_runtime_contract.py`

**Interfaces:**
- Production preflight accepts only Brevo and cap <=300.
- Controlled test records external quota before bounded event polling and only succeeds on `delivered`.
- [ ] **Step 1: Write RED runtime tests**

```python

def test_worker_unit_is_brevo_specific():
    text = WORKER_UNIT.read_text(encoding="utf-8")
    assert "Brevo Free" in text
    assert "Microsoft Graph" not in text


def test_controlled_test_requires_real_delivery():
    source = TEST_SCRIPT.read_text(encoding="utf-8")
    assert "brevo_controlled_test" in source
    assert '"delivered"' in source
    assert "envios_externos_cota" in source
```

Also assert the preflight requires `EMAIL_PROVIDER=brevo`, `BREVO_API_KEY`, fixed sender, and effective max/meta <=300.

- [ ] **Step 2: Implement preflight, controlled test and documentation**
The controlled send target defaults to `atendimento@shopvivaliz.com.br`, uses the existing approved template, inserts its accepted Brevo ID in `envios_externos_cota`, then polls only that raw message ID until `delivered`, a terminal permanent failure, or a bounded timeout.

- [ ] **Step 3: Full local validation, guard, commit and immediate push**

```text
py -3 -m pytest -q
py -3 scripts/repo_policy_guard.py
git status --porcelain=v1
git add app worker scripts deploy tests README.md AGENTS.md
git commit -m "chore: complete Brevo production cutover contract"
git push origin feat/brevo-free-300
```

### Task 5: PR, production cutover and real smoke validation

**Files/Systems:** GitHub PR/Actions, production VM `always-free-arm-1787907847-26`, protected runtime `.env`, Brevo account.

- [ ] **Step 1: Open PR and complete independent validation**
Open one PR from `feat/brevo-free-300` to `main`. Inspect every check; fix failures with TDD, guard, commit and immediate push. Merge only the exact validated head SHA. Verify the resulting main SHA has no failed/pending relevant Actions.

- [ ] **Step 2: Materialize the existing Brevo secret without exposing it**
Use the existing ShopVivaLiz GitHub secret/workflow or privileged Fred-Win SSH path. Validate key presence by length/non-empty only and query Brevo sender metadata without printing the key. Keep the migration pause sentinel present.

- [ ] **Step 3: Deploy merged main fail-closed**
Update production to the merged SHA, set `EMAIL_PROVIDER=brevo`, `MAX_ENVIOS_POR_DIA=300`, `META_ENVIOS_POR_DIA=295`, deploy systemd units, disable Exchange NDR guard, enable Brevo reconciler, and run policy/runtime preflights. Do not remove the pause sentinel yet.

- [ ] **Step 4: Run controlled real-delivery proof**
Run `scripts/enviar_teste_brevo.py`. Require API acceptance with stored `brevo:<messageId>`, external quota record, and a real Brevo `delivered` event. Verify reconciler and monitor health.

- [ ] **Step 5: Resume safely and verify 300/24h invariant**
Remove only the migration pause sentinel after the proof passes, restart/recycle worker through the approved privileged path, and verify logs/DB show Brevo-only new submissions. Assert rolling Brevo count is <=300, effective max=300/meta=295, no Graph submission path is active, and no duplicate recipient is generated.

- [ ] **Step 6: Final repository and task-manager closure**
Confirm `git status --porcelain=v1` clean, no open relevant PRs, no failed/pending relevant Actions, production services healthy, and Plate task FRE-74 fully checked/completed.