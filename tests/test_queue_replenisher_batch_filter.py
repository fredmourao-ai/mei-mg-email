from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_replenisher_filters_each_page_against_canonical_contract():
    src = (ROOT / "scripts/queue_replenisher.py").read_text(encoding="utf-8")
    body = src.split("def filter_candidates_batch", 1)[1].split("def collect_candidates", 1)[0]
    fetch_body = src.split("def fetch_page", 1)[1].split("def filter_candidates_batch", 1)[0]
    assert "opt_out" in fetch_body
    for token in ("is_valid_email_address", "is_email_suppressed", "is_cnpj_suppressed", "ACTIVE_STATUSES", "limit 3", "contabil"):
        assert token in body
    legacy_authorization = "marketing_" + "autorizado"
    for retired in (legacy_authorization, "mei_verificado", "tipo_regime", "provavel_terceiro"):
        assert retired not in body


def test_replenisher_filters_page_with_bounded_set_based_queries():
    src = (ROOT / "scripts/queue_replenisher.py").read_text(encoding="utf-8")
    body = src.split("def filter_candidates_batch", 1)[1].split("def collect_candidates", 1)[0]
    assert "unnest(" in body.lower()
    assert "row_number() over" in body.lower()
    assert "for row in rows" in body
    assert "select cnpj" in body.lower()
    assert "select distinct lower(btrim(email::text))" in body.lower()


def test_replenisher_anti_replay_uses_indexable_separate_lookups():
    src = (ROOT / "scripts/queue_replenisher.py").read_text(encoding="utf-8")
    body = src.split("def filter_candidates_batch", 1)[1].split("def collect_candidates", 1)[0]
    assert "prior_cnpjs as materialized" in body.lower()
    assert "prior_emails as materialized" in body.lower()
    assert "lower(btrim(email::text)) = any(%s::text[])" in body


def test_replenisher_batch_filter_precomputes_expensive_membership_sets():
    src = (ROOT / "scripts" / "queue_replenisher.py").read_text(encoding="utf-8")
    body = src.split("def filter_candidates_batch", 1)[1].split("def collect_candidates", 1)[0]
    lowered = body.lower()

    assert "join mei_email.empresas e" not in lowered
    assert "shared_email_counts" in lowered
    assert "prior_cnpjs as materialized" in lowered
    assert "prior_emails as materialized" in lowered
    assert "(select count(*)" not in lowered
    assert "not exists (" not in lowered
