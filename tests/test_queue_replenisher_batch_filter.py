from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_replenisher_filters_each_page_against_canonical_contract():
    src = (ROOT / "scripts/queue_replenisher.py").read_text(encoding="utf-8")
    body = src.split("def filter_candidates_batch", 1)[1].split("def collect_candidates", 1)[0]
    for token in ("is_valid_email_address", "opt_out", "is_email_suppressed", "is_cnpj_suppressed", "ACTIVE_STATUSES", "limit 3", "contabil"):
        assert token in body
    for retired in ("marketing_autorizado", "mei_verificado", "tipo_regime", "provavel_terceiro"):
        assert retired not in body
