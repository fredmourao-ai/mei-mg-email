from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_autorepair_service_runs_lightweight_supervisor():
    service = (ROOT / "deploy/systemd/mei-mg-email-autorepair.service").read_text()
    timer = (ROOT / "deploy/systemd/mei-mg-email-autorepair.timer").read_text()
    assert "scripts/nonstop_supervisor_15m.py" in service
    assert "autocorrigir_envios_guarded.py" not in service
    assert "TimeoutStartSec=90" in service
    assert "OnUnitActiveSec=15min" in timer
    assert "Persistent=true" in timer


def test_supervisor_never_clears_sentinel_or_mutates_queue():
    src = (ROOT / "scripts/nonstop_supervisor_15m.py").read_text()
    assert "sender_blocked.pause" in src
    assert "worker_stopped_for_current_sender_block" in src
    assert '"restart"' in src
    assert '"enable"' in src
    assert "unlink(" not in src
    assert "remove(" not in src
    assert "delete from" not in src.lower()
    assert "update mei_email" not in src.lower()
    assert "insert into" not in src.lower()
    assert "provider.send" not in src
    assert "select 1" in src
