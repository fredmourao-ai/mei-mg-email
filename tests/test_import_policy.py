from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def normalized(path: str) -> str:
    return " ".join((ROOT / path).read_text(encoding="utf-8").casefold().split())


def test_existing_database_is_authorized_and_operator_verified():
    sql = normalized("db/migrations/V022__operator_authorize_and_verify_existing_base.sql")
    assert "marketing_autorizado = true" in sql
    assert "mei_verificado = true" in sql
    assert "confirmacao_operador_2026-08-13" in sql
    assert "override_operador_2026-08-13" in sql
    assert "e.opt_out = false" in sql


def test_new_imports_receive_operator_policy_flags():
    sql = normalized("db/migrations/V023__auto_authorize_and_verify_new_imports.sql")
    assert "new.marketing_autorizado := true" in sql
    assert "new.mei_verificado := true" in sql
    assert "before insert on empresas" in sql
    assert "politica_importacao_operador_2026-08-13" in sql
    assert "opt-out nao e alterado" in sql


def test_runtime_sender_pause_is_not_versioned():
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "runtime/" in ignore
    assert not (ROOT / "runtime" / "sender_blocked.pause").exists()
