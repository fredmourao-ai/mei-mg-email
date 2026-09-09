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


def test_worker_rolling_quota_uses_statement_time_not_transaction_time():
    quota_fn = SRC.split("def _obter_envios_ultimas_24h_indexado", 1)[1]
    quota_fn = quota_fn.split("def _ja_submetido_ou_entregue_indexado", 1)[0]
    assert "statement_timestamp() - interval '24 hours'" in quota_fn
    assert "now() - interval '24 hours'" not in quota_fn


def test_worker_releases_transaction_before_quota_wait():
    loop = SRC.split("while True:", 1)[1]
    branch = loop.split("if envios_24h >= limite_24h:", 1)[1].split("# Existing queue always wins.", 1)[0]
    rollback_pos = branch.find("conn.rollback()")
    sleep_pos = branch.find("time.sleep(max(settings.worker_poll_interval_segundos, 60))")
    assert rollback_pos >= 0
    assert rollback_pos < sleep_pos


def test_worker_releases_transaction_before_idle_poll_wait():
    loop = SRC.split("while True:", 1)[1]
    tail = loop.split("if not _processar_se_disponivel(conn, provider):", 1)[1]
    assert "conn.rollback()" in tail.split("time.sleep(settings.worker_poll_interval_segundos)", 1)[0]
