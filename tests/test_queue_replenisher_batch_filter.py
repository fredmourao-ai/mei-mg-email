from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_replenisher_filters_each_page_against_canonical_contract():
    src = (ROOT / "scripts/queue_replenisher.py").read_text(encoding="utf-8")
    body = src.split("def filter_candidates_batch", 1)[1].split("def collect_candidates", 1)[0]
    for token in ("is_valid_email_address", "opt_out", "is_email_suppressed", "is_cnpj_suppressed", "ACTIVE_STATUSES", "limit 3", "contabil"):
        assert token in body
    for retired in ("marketing_autorizado", "mei_verificado", "tipo_regime", "provavel_terceiro"):
        assert retired not in body


def test_replenisher_filters_page_in_one_set_based_query():
    src = (ROOT / "scripts/queue_replenisher.py").read_text(encoding="utf-8")
    body = src.split("def filter_candidates_batch", 1)[1].split("def collect_candidates", 1)[0]
    assert "unnest(" in body.lower()
    assert body.count("cur.execute(") == 1
    assert "row_number() over" in body.lower()


def test_replenisher_anti_replay_uses_indexable_separate_lookups():
    src = (ROOT / "scripts/queue_replenisher.py").read_text(encoding="utf-8")
    body = src.split("def filter_candidates_batch", 1)[1].split("def collect_candidates", 1)[0]
    assert body.lower().count("not exists (") >= 2
    assert "lower(btrim(x.email::text)) = lower(btrim(e.email::text))" in body
