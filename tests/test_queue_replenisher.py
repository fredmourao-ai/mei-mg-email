from pathlib import Path

from app.config import settings
from app.queue_manager import quantidade_para_repor

ROOT = Path(__file__).resolve().parents[1]


def test_continuous_queue_defaults_keep_nonzero_buffer():
    assert settings.queue_min_pending == 1000
    assert settings.queue_target_pending == 5000
    assert settings.queue_min_pending >= 1
    assert settings.queue_target_pending > settings.queue_min_pending


def test_replenisher_refills_before_queue_reaches_zero():
    assert quantidade_para_repor(0) == 5000
    assert quantidade_para_repor(500) == 4500
    assert quantidade_para_repor(1000) == 4000
    assert quantidade_para_repor(1001) == 0
    assert quantidade_para_repor(5000) == 0


def test_worker_replenishes_before_fetching_next_lot():
    worker = (ROOT / "worker" / "worker.py").read_text(encoding="utf-8")
    refill = worker.index("repor_fila_automatica(conn)")
    fetch = worker.index("lote = pegar_proximo_lote(conn)", refill)
    assert refill < fetch


def test_queue_is_separate_from_24h_send_quota_in_audit():
    audit = (ROOT / "scripts" / "auditar_exchange_10000.py").read_text(
        encoding="utf-8"
    )
    assert "fila_compromete_acima_meta" not in audit
    assert "queue_target_pending" in audit
    assert "submitted_ou_enviados_ultimas_24h" in audit


def test_legacy_daily_script_uses_continuous_replenisher():
    script = (ROOT / "scripts" / "disparar_10000_mei_mg.py").read_text(
        encoding="utf-8"
    )
    assert "repor_fila_automatica" in script
    assert "EXPECTED_DAILY_TARGET = 9950" in script
