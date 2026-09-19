import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "brevo_event_reconciler.py"


def _load_module():
    assert SCRIPT.exists(), "Brevo reconciler script must exist"
    spec = importlib.util.spec_from_file_location("brevo_event_reconciler_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_delivered_event_maps_to_delivered():
    module = _load_module()
    outcome = module.classify_event({"event": "delivered"})
    assert outcome.status == "delivered"
    assert outcome.suppress is False


def test_permanent_brevo_failures_create_hard_bounce():
    module = _load_module()
    for event in ("hardBounce", "hardbounces", "invalid", "blocked", "spam"):
        outcome = module.classify_event({"event": event, "reason": "x"})
        assert outcome.status == "bounce_permanent"
        assert outcome.suppress is True


def test_transient_and_engagement_events_do_not_reopen_delivery():
    module = _load_module()
    for event in ("softBounce", "deferred", "sent", "request", "opened", "click"):
        outcome = module.classify_event({"event": event})
        assert outcome.status is None
        assert outcome.suppress is False


def test_brevo_event_uses_provider_attributed_storage_id():
    module = _load_module()
    assert module.storage_message_id({"messageId": "<abc@example>"}) == "brevo:<abc@example>"


def test_duplicate_event_keys_are_stable_and_deduplicated():
    module = _load_module()
    event = {
        "messageId": "<abc@example>",
        "event": "delivered",
        "date": "2026-09-06T12:00:00Z",
        "email": "owner@example.com",
    }
    key = module.event_key(event)
    assert key == module.event_key(dict(event))
    unique, seen = module.dedupe_events([event, dict(event)], set())
    assert unique == [event]
    assert key in seen


def test_reconciler_persists_only_brevo_attributed_rows_and_suppresses_permanent():
    source = SCRIPT.read_text(encoding="utf-8") if SCRIPT.exists() else ""
    assert "provider_message_id = %s" in source
    assert "brevo_event_reconciler" in source
    assert "register_operational_suppression" in source
    assert "bounce_permanent" in source
    assert "STATE_PATH" in source
    assert "MAX_PAGES" in source


def test_unmatched_terminal_event_is_retried_instead_of_marked_seen(monkeypatch):
    module = _load_module()
    event = {
        "messageId": "<race@example>",
        "event": "delivered",
        "date": "2026-09-06T12:00:00Z",
        "email": "owner@example.com",
    }

    class DummyConnection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    saved = {}
    monkeypatch.setattr(module, "fetch_events", lambda: [event])
    monkeypatch.setattr(module, "_load_state", lambda: {"seen_event_keys": []})
    monkeypatch.setattr(module, "_save_state", lambda state: saved.update(state))
    monkeypatch.setattr(module.psycopg, "connect", lambda *args, **kwargs: DummyConnection())
    monkeypatch.setattr(module, "apply_event", lambda conn, value: False)
    module.process_once()
    assert module.event_key(event) not in saved["seen_event_keys"]


def test_external_quota_ledger_delivery_is_reconciled():
    module = _load_module()
    event = {
        "messageId": "<controlled@example>",
        "event": "delivered",
        "date": "2026-09-08T12:00:00Z",
        "email": "owner@example.com",
    }

    class Cursor:
        def __init__(self):
            self.next_row = None
            self.executed = []

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, sql, params=None):
            normalized = " ".join(sql.split())
            self.executed.append((normalized, params))
            if "from mei_email.envios_externos_cota" in normalized:
                self.next_row = ("external-id", "owner@example.com")
            elif "from mei_email.envios" in normalized:
                self.next_row = None
            else:
                self.next_row = None

        def fetchone(self):
            return self.next_row

    class Connection:
        def __init__(self):
            self.cur = Cursor()
            self.commits = 0
            self.rollbacks = 0

        def cursor(self):
            return self.cur

        def commit(self):
            self.commits += 1

        def rollback(self):
            self.rollbacks += 1

    conn = Connection()
    assert module.apply_event(conn, event) is True
    assert conn.commits == 1
    assert conn.rollbacks == 0
    updates = [sql for sql, _ in conn.cur.executed if "update mei_email.envios_externos_cota" in sql]
    assert updates
    assert "brevo_delivery_status" in updates[0]
    assert "brevo_event_key" in updates[0]

def test_state_upgrade_reprocesses_once_and_then_converges(monkeypatch):
    module = _load_module()
    monkeypatch.setattr(module, "MAX_SEEN_KEYS", 3)
    event = {
        "messageId": "<fresh@example>",
        "event": "requests",
        "date": "2026-09-19T05:00:00Z",
        "email": "owner@example.com",
    }
    store = {"seen_event_keys": ["old-a", "old-b", "old-c"]}

    class DummyConnection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(module, "fetch_events", lambda: [event])
    monkeypatch.setattr(module, "_load_state", lambda: dict(store))
    monkeypatch.setattr(module, "_save_state", lambda state: (store.clear(), store.update(state)))
    monkeypatch.setattr(module.psycopg, "connect", lambda *args, **kwargs: DummyConnection())

    first = module.process_once()
    assert first["schema_version"] == module.STATE_SCHEMA_VERSION
    assert first["last_unique"] == 1
    assert module.event_key(event) in first["seen_event_keys"]

    second = module.process_once()
    assert second["last_unique"] == 0
    assert second["seen_event_keys"] == first["seen_event_keys"]


def test_reconciler_preserves_first_reconciliation_evidence():
    source = SCRIPT.read_text(encoding="utf-8")
    normalized = " ".join(source.split())
    assert "reconciled_at = coalesce(reconciled_at, now())" in normalized
    assert "metadata->'brevo_reconciled_at'" in normalized
    assert "coalesce(metadata->>'brevo_event_key', '') <> %s" in normalized
