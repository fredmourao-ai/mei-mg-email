from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_bulk_recovery_prunes_ineligible_open_rows_before_worker_loop():
    source = (ROOT / "app" / "queue_recovery.py").read_text(encoding="utf-8")
    for token in (
        "emp.opt_out = true",
        "emp.situacao_cadastral <> 'ATIVA'",
        "emp.provavel_terceiro = true",
        "emp.marketing_autorizado = false",
        "emp.mei_verificado = false",
        "not mei_email.is_valid_email_address(e.email)",
        "discarded_ineligible",
    ):
        assert token in source


def test_bulk_prune_counts_toward_recovery_change_signal():
    source = (ROOT / "app" / "queue_recovery.py").read_text(encoding="utf-8")
    assert "self.discarded_ineligible" in source
    assert "self.discarded_already_suppressed" in source
    assert "self.discarded_open_duplicates" in source
    assert "self.closed_empty_lots" in source
