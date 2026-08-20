from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_v2_keeps_fail_closed_lot_prune_enabled():
    source = (ROOT / "worker" / "safe_entrypoint_v2.py").read_text(encoding="utf-8")
    assert "base.worker.processar_lote = base._safe_processar_lote" in source
    assert "base.worker.processar_lote = base._ORIGINAL_PROCESSAR_LOTE" not in source


def test_presend_prune_removes_rejected_rows_then_continues_lot():
    source = (ROOT / "worker" / "safe_entrypoint.py").read_text(encoding="utf-8")
    prune_start = source.index("def _safe_processar_lote")
    prune_body = source[prune_start : source.index("\n\nworker.base_worker.montar_corpo", prune_start)]
    assert "removed = _prune_lot(conn, lote[\"id\"])" in prune_body
    assert "_ORIGINAL_PROCESSAR_LOTE(conn, lote, provider)" in prune_body


def test_surviving_recipient_still_gets_final_presend_checkpoint():
    source = (ROOT / "worker" / "safe_entrypoint.py").read_text(encoding="utf-8")
    assert "worker._marcar_envio_em_transito = _safe_mark" in source
    safe_mark = source[source.index("def _safe_mark") : source.index("\n\ndef _safe_recovery")]
    assert "ok, reason = _eligibility(conn, envio_id)" in safe_mark
    assert "_drop_never_dispatched(conn, envio_id, reason)" in safe_mark
    assert "_ORIGINAL_MARK(conn, envio_id)" in safe_mark
