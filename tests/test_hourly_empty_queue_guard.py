from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_hourly_service_uses_empty_queue_guard():
    service = (
        ROOT / "deploy" / "systemd" / "mei-mg-email-autorepair.service"
    ).read_text(encoding="utf-8")
    assert "scripts/autocorrigir_envios_hourly.py" in service
    assert "autocorrigir_envios_2h.py --apply" not in service


def test_empty_queue_guard_is_bounded_and_fail_closed():
    source = (ROOT / "scripts" / "autocorrigir_envios_hourly.py").read_text(
        encoding="utf-8"
    )
    assert "AUTOREPAIR_EMPTY_QUEUE_RETRIES" in source
    assert "EMPTY_QUEUE_RETRIES + 1" in source
    assert "repor_fila_automatica_isolada()" in source
    assert "failed_empty_queue_below_target" in source
    assert "current sender-block sentinel present; automatic resume is forbidden" in source
    assert "unlink(" not in source
    assert "remove(" not in source


def test_empty_queue_guard_never_forces_target_without_authorized_candidates():
    source = (ROOT / "scripts" / "autocorrigir_envios_hourly.py").read_text(
        encoding="utf-8"
    )
    assert "queue_sent_before" in source
    assert "final.get(\"queue_sent_24h\")" in source
    assert "_below_target_and_empty(final)" in source
    assert "_authorized_candidate_exists" in source
    assert "vw_empresas_elegiveis" in source
    assert "authorized_candidate_available" in source
    assert "healthy_authorized_pool_exhausted" in source
    assert "healthy_or_progressing" in source
