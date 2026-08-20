from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_autoqueue_keeps_raw_boolean_predicates_for_partial_index():
    src = (ROOT / "app/queue_manager.py").read_text()
    assert "and e.marketing_autorizado = true" in src
    assert "and e.mei_verificado = true" in src
    assert "is_independent_marketing_authorization" in src
    assert "is_independent_mei_verification" in src


def test_partial_index_uses_same_raw_boolean_contract():
    sql = (ROOT / "db/migrations/V029__autoqueue_partial_index.sql").read_text()
    assert "marketing_autorizado = true" in sql
    assert "mei_verificado = true" in sql
    assert "idx_empresas_autoqueue_mei_mg" in sql
