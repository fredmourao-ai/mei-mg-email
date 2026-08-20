from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_worker_unit_uses_bounded_preflight_and_safe_entrypoint():
    unit = (ROOT / "deploy/systemd/mei-mg-email-worker.service").read_text()
    assert "StartLimitIntervalSec=0" in unit
    assert "Restart=always" in unit
    assert "RestartSec=5" in unit
    assert "TimeoutStartSec=30" in unit
    assert "scripts/runtime_sender_preflight.py" in unit
    assert "-m worker.safe_entrypoint_v2" in unit
    assert "scripts/runtime_sender_guard.py" not in unit


def test_preflight_is_read_only_and_never_bulk_rewrites_queue():
    src = (ROOT / "scripts/runtime_sender_preflight.py").read_text().lower()
    assert "update mei_email.campanhas" not in src
    assert "update mei_email.envios" not in src
    assert "delete from mei_email.envios" not in src
    assert "insert into" not in src
    assert "marketing_autorizado_origem" in src
    assert "mei_verificado_origem" in src
    assert "statement_timeout='5s'" in src


def test_safe_entrypoint_checks_independent_sources_replay_and_copy_before_graph():
    src = (ROOT / "worker/safe_entrypoint.py").read_text()
    assert "LEGACY_MARKETING_ORIGINS" in src
    assert "operator_authorization_true_2026-08-20" in src
    assert "LEGACY_MEI_ORIGINS" in src
    assert "email_suppressions" in src
    assert "terminal_history" in src
    assert "envios_externos_cota" in src
    assert "_marcar_envio_em_transito = _safe_mark" in src
    assert "status='submitted'" in src
    assert "resultado Graph incerto" in src
    assert "worker.base_worker.montar_corpo = _safe_render" in src
    assert "base pública de CNPJ" in src
    assert "autorização comercial registrada" in src
    recovery = src.split("def _safe_recovery", 1)[1].split("def _prune_lot", 1)[0]
    assert "status='pendente'" not in recovery


def test_v2_uses_indexable_suppression_value_lookup_and_rejects_operator_inferred_auth():
    src = (ROOT / "worker/safe_entrypoint_v2.py").read_text()
    assert "s.value=lower(btrim(e.email::text))::public.citext" in src
    assert "lower(btrim(s.value))" not in src
    assert "operator_authorization_true" in src
    assert "_disallowed_marketing_origin" in src
