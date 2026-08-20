from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_runtime_sender_guard_is_batched_and_fail_closed():
    source = (ROOT / "scripts" / "runtime_sender_guard.py").read_text(encoding="utf-8")
    normalized = " ".join(source.split())
    assert "RUNTIME_GUARD_BATCH_SIZE" in source
    assert "for update of e skip locked" in normalized
    assert "limit %s" in normalized
    assert "statement_timeout='15s'" in source
    assert "statement_timeout='60s'" not in source
    assert "marketing_autorizado_origem" in source
    assert "mei_verificado_origem" in source
    assert "base pública de CNPJ" in source
    assert "delete from mei_email.envios e" in normalized
    assert "status='bloqueado'::mei_email.status_envio" not in source
    assert "pg_advisory_lock" in source
    assert "pg_advisory_unlock" in source


def test_runtime_sender_guard_preserves_uncertain_dispatch_and_company_state():
    source = (ROOT / "scripts" / "runtime_sender_guard.py").read_text(encoding="utf-8")
    normalized = " ".join(source.casefold().split())
    assert "queued_sql = \"('pendente','pending','processing')\"" in normalized
    assert "uncertain_dispatch" in source
    assert "delete from mei_email.empresas" not in normalized


def test_runtime_sender_guard_never_grants_consent_or_clears_sender_block():
    source = (ROOT / "scripts" / "runtime_sender_guard.py").read_text(encoding="utf-8")
    normalized = " ".join(source.casefold().split())
    assert "set marketing_autorizado" not in normalized
    assert "set mei_verificado" not in normalized
    assert "sender_blocked.pause" not in source
    assert "unlink(" not in source
