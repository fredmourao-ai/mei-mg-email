from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / 'scripts' / 'queue_replenisher.py').read_text(encoding='utf-8')


def section(start: str, end: str) -> str:
    return SRC.split(start, 1)[1].split(end, 1)[0]


def test_fetch_page_only_uses_cheap_scan_predicates():
    body = section('def fetch_page', 'def filter_candidates_batch')
    assert 'is_valid_email_address' not in body
    assert "position('contabil'" not in body
    assert "situacao_cadastral = 'ATIVA'" in body
    assert "coalesce(e.opt_out,false)=false" in body.replace(' ', '')
    assert 'order by e.cnpj' in body


def test_batch_filter_matches_canonical_live_guard():
    body = section('def filter_candidates_batch', 'def collect_candidates')
    for token in (
        'is_valid_email_address', "'contabil' in norm",
        'is_email_suppressed', 'is_cnpj_suppressed',
        'limit 3', 'ACTIVE_STATUSES', 'mei_email.status_envio[]',
    ):
        assert token in body
