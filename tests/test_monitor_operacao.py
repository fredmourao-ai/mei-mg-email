from pathlib import Path

from scripts.monitor_operacao import construir_alertas

ROOT = Path(__file__).resolve().parents[1]


def snapshot_base():
    return {
        "limits": {
            "meta_24h": 300,
            "max_24h": 300,
            "rate_per_minute": 10,
            "queue_min_pending": 14800,
            "queue_target_pending": 15000,
        },
        "queue": {
            "total": 14900,
            "pendentes": 14900,
            "enviando": 0,
            "ineligible_open": 0,
            "elegiveis_restantes": 50000,
        },
        "sending": {
            "submitted_enviado_24h": 200,
            "submitted_enviado_60m": 20,
            "submitted_enviado_15m": 5,
            "submitted_enviado_5m": 2,
            "last_submission_at": "2026-08-12T12:00:00+00:00",
            "last_submission_age_minutes": 0.2,
            "failures_24h": 2,
            "sender_blocked_24h": 0,
        },
        "worker": {
            "advisory_lock_held": True,
            "systemd_active": "active",
            "sender_block_pause_active": False,
            "sender_block_pause_path": "/var/lib/mei-mg-email/sender_blocked.pause",
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




def test_ineligible_open_queue_is_critical():
    snapshot = snapshot_base()
    snapshot["queue"]["ineligible_open"] = 3
    assert "queue_ineligible_open" in codes(snapshot)


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
    snapshot["sending"]["submitted_enviado_24h"] = 300
    snapshot["sending"]["submitted_enviado_15m"] = 0
    snapshot["sending"]["last_submission_age_minutes"] = 60.0
    assert "sending_stalled" not in codes(snapshot)


def test_missing_worker_lock_is_detected_when_work_is_expected():
    snapshot = snapshot_base()
    snapshot["worker"]["advisory_lock_held"] = False
    assert "worker_lock_missing" in codes(snapshot)


def test_sender_pause_explains_intentional_worker_stop():
    snapshot = snapshot_base()
    snapshot["worker"]["sender_block_pause_active"] = True
    snapshot["worker"]["advisory_lock_held"] = False
    snapshot["sending"]["submitted_enviado_15m"] = 0
    snapshot["sending"]["last_submission_age_minutes"] = 60.0
    result = codes(snapshot)
    assert "sender_block_pause_active" in result
    assert "worker_lock_missing" not in result
    assert "sending_stalled" not in result


def test_brevo_reconciler_failure_is_critical_from_base_snapshot():
    snapshot = snapshot_base()
    snapshot["worker"]["brevo_reconciler_active"] = "failed"
    snapshot["worker"]["brevo_reconciler_enabled"] = "disabled"
    result = codes(snapshot)
    assert "brevo_reconciler_not_active" in result
    assert "brevo_reconciler_not_enabled" in result


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

def test_worker_lock_held_supports_dict_row():
    from scripts.monitor_operacao import _worker_lock_held

    class Cursor:
        def execute(self, *args, **kwargs):
            return None

        def fetchone(self):
            return {"exists": True}

    assert _worker_lock_held(Cursor()) is True


def test_hard_bounce_baseline_does_not_alert_without_material_worsening():
    snapshot = snapshot_base()
    snapshot["sending"].update({
        "hard_bounces_15m": 8,
        "hard_bounces_60m": 30,
        "hard_bounces_24h": 280,
        "hard_bounce_rate_60m_pct": 5.0,
        "hard_bounce_rate_24h_pct": 7.0,
    })
    assert "hard_bounce_rate_worsening" not in codes(snapshot)


def test_material_hard_bounce_rate_worsening_is_detected():
    snapshot = snapshot_base()
    snapshot["sending"].update({
        "hard_bounces_15m": 35,
        "hard_bounces_60m": 120,
        "hard_bounces_24h": 280,
        "hard_bounce_rate_60m_pct": 20.0,
        "hard_bounce_rate_24h_pct": 7.0,
    })
    assert "hard_bounce_rate_worsening" in codes(snapshot)


def test_brevo_reconciler_failure_is_critical():
    snapshot = snapshot_base()
    snapshot["worker"]["brevo_reconciler_active"] = "failed"
    snapshot["worker"]["brevo_reconciler_enabled"] = "disabled"
    result = codes(snapshot)
    assert "brevo_reconciler_not_active" in result
    assert "brevo_reconciler_not_enabled" in result


def test_monitor_uses_brevo_hard_bounce_source():
    source = (ROOT / "scripts" / "monitor_operacao.py").read_text(encoding="utf-8")
    assert "brevo_event_reconciler" in source


def test_monitor_counts_brevo_quota_by_submission_evidence_not_final_status():
    source = (ROOT / "scripts" / "monitor_operacao.py").read_text(encoding="utf-8").casefold()
    assert "provider_message_id like 'brevo:%'" in source
    assert "submitted_at" in source


def test_long_running_base_sync_is_healthy_while_service_is_active():
    snapshot = snapshot_base()
    snapshot["base_sync"]["latest"] = {"status": "running"}
    snapshot["base_sync"]["age_hours"] = 7.0
    snapshot["base_sync"]["service_active"] = "active"
    assert "base_sync_stuck" not in codes(snapshot)
    assert "base_sync_orphaned" not in codes(snapshot)


def test_running_base_sync_without_service_is_orphaned():
    snapshot = snapshot_base()
    snapshot["base_sync"]["latest"] = {"status": "running"}
    snapshot["base_sync"]["age_hours"] = 7.0
    snapshot["base_sync"]["service_active"] = "inactive"
    assert "base_sync_orphaned" in codes(snapshot)


def test_queue_replenisher_service_failure_is_critical():
    snapshot = snapshot_base()
    snapshot["worker"]["queue_replenisher_active"] = "inactive"
    snapshot["worker"]["queue_replenisher_enabled"] = "disabled"
    result = codes(snapshot)
    assert "queue_replenisher_not_active" in result
    assert "queue_replenisher_not_enabled" in result


def test_absolute_hard_bounce_rate_above_brevo_limit_is_critical():
    snapshot = snapshot_base()
    snapshot["sending"].update({
        "submitted_enviado_24h": 100,
        "hard_bounces_24h": 3,
        "hard_bounce_rate_24h_pct": 3.0,
        "hard_bounces_60m": 0,
        "hard_bounce_rate_60m_pct": 0.0,
    })
    alerts = construir_alertas(snapshot)
    assert any(
        item["code"] == "hard_bounce_rate_excessive" and item["level"] == "critical"
        for item in alerts
    )
