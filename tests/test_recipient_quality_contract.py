from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_replenisher_applies_obvious_provider_typo_guard():
    src = (ROOT / "scripts" / "queue_replenisher.py").read_text(encoding="utf-8")
    body = src.split("def filter_candidates_batch", 1)[1].split("def collect_candidates", 1)[0]
    assert "recipient_has_obvious_provider_typo" in body


def test_worker_blocks_obvious_provider_typo_before_dispatch_checkpoint():
    src = (ROOT / "worker" / "worker_queue_first.py").read_text(encoding="utf-8")
    body = src.split("def processar_lote", 1)[1].split("def _processar_se_disponivel", 1)[0]
    guard_pos = body.find("recipient_has_obvious_provider_typo")
    checkpoint_pos = body.find("_marcar_envio_em_transito")
    assert guard_pos >= 0
    assert checkpoint_pos >= 0
    assert guard_pos < checkpoint_pos
