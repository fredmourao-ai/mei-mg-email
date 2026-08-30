from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / 'worker' / 'worker_queue_first.py').read_text(encoding='utf-8')


def test_partial_lot_uses_total_rows_before_processing_as_invariant():
    assert 'expected_db_total' in SRC
    assert 'select count(*) from mei_email.envios where lote_id = %s' in SRC
    assert 'total_db != expected_db_total' in SRC
    assert 'expected_db = len(envios)' not in SRC


def test_lot_validation_allows_open_rows_added_after_snapshot():
    assert 'or abertos or sem_prova' not in SRC
    assert 'or sem_prova' in SRC