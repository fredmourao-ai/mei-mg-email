from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "worker" / "worker_queue_first.py").read_text(encoding="utf-8")


def test_worker_checks_full_24h_quota_before_taking_queue_work():
    loop = SRC.split("while True:", 1)[1]
    quota_pos = loop.find("_obter_envios_ultimas_24h_indexado(conn)")
    work_pos = loop.find("_processar_se_disponivel(conn, provider)")
    assert quota_pos >= 0
    assert work_pos >= 0
    assert quota_pos < work_pos
    between = loop[quota_pos:work_pos]
    assert "time.sleep(max(settings.worker_poll_interval_segundos, 60))" in between
