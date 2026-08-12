from pathlib import Path

from scripts.monitor_operacao import construir_alertas

ROOT = Path(__file__).resolve().parents[1]


def snapshot_base():
    return {
        "limits": {
            "meta_24h": 9950,
            "max_24h": 10000,
            "rate_per_minute": 30,
            "queue_min_pending": 1000,
            "queue_target_pending": 5000,
        },
        "queue": {
            "total": 3000,
            "pendentes": 3000,
            "enviando": 0,
            "elegiveis_restantes": 50000,
        },
        "sending": {
            "submitted_enviado_24h": 4000,
            "submitted_enviado_60m": 900,
            "submitted_enviado_15m": 225,
            "submitted_enviado_5m": 75,
            "last_submission_at": "2026-08-12T12:00:00+00:00",
            "last_submission_age_minutes": 0.2,
            "failures_24h": 2,
            "sender_blocked_24h": 0,
        },
        "worker": {
            "advisory_lock_held": True,
            "systemd_active": "active",
        },
        "base_sync": {
            "latest": {"status": "success"},
            "age_hours": 4.0,
            "timer_active": "active",
            "timer_enabled": "enabled",
        },
    }


def codes(snapshot):
    return {alert["code"] for alert in construir_alertas(snapshot)}


def test_healthy_monitor_has_no_alerts():
    assert construir_alertas(snapshot_base()) == []


def test_empty_queue_is_critical():
    snapshot = snapshot_base()
    snapshot["queue"]["total"] = 0
    assert "queue_empty" in codes(snapshot)


def test_stalled_send_with_queue_and_capacity_is_detected():
    snapshot = snapshot_base()
    snapshot["sending"]["submitted_enviado_15m"] = 0
    snapshot["sending"]["last_submission_age_minutes"] = 15.0
    assert "sending_stalled" in codes(snapshot)


def test_quota_reached_does_not_report_stalled_send():
    snapshot = snapshot_base()
    snapshot["sending"]["submitted_enviado_24h"] = 9950
    snapshot["sending"]["submitted_enviado_15m"] = 0
    snapshot["sending"]["last_submission_age_minutes"] = 60.0
    assert "sending_stalled" not in codes(snapshot)


def test_missing_worker_lock_is_detected_when_work_is_expected():
    snapshot = snapshot_base()
    snapshot["worker"]["advisory_lock_held"] = False
    assert "worker_lock_missing" in codes(snapshot)


def test_base_sync_overdue_and_timer_disabled_are_detected():
    snapshot = snapshot_base()
    snapshot["base_sync"]["age_hours"] = 30.0
    snapshot["base_sync"]["timer_active"] = "inactive"
    snapshot["base_sync"]["timer_enabled"] = "disabled"
    result = codes(snapshot)
    assert "base_sync_overdue" in result
    assert "base_timer_not_active" in result
    assert "base_timer_not_enabled" in result


def test_sender_blocked_is_always_critical():
    snapshot = snapshot_base()
    snapshot["sending"]["sender_blocked_24h"] = 1
    assert "sender_blocked" in codes(snapshot)


def test_systemd_timer_is_persistent_and_daily():
    timer = (ROOT / "deploy" / "systemd" / "mei-mg-email-base-sync.timer").read_text(encoding="utf-8")
    assert "Persistent=true" in timer
    assert "OnCalendar=*-*-* 03:15:00 America/Sao_Paulo" in timer


def test_monitor_runs_as_separate_restartable_service():
    service = (ROOT / "deploy" / "systemd" / "mei-mg-email-monitor.service").read_text(encoding="utf-8")
    assert "ExecStart=__PYTHON__ scripts/monitor_operacao.py" in service
    assert "Restart=always" in service
