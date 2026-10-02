from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "operational_retention_maintenance.py"
UNIT = ROOT / "deploy" / "systemd" / "mei-mg-email-retention-maintenance.service"


def test_retention_is_dry_run_by_default_and_apply_is_fail_closed():
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'parser.add_argument("--apply", action="store_true")' in text
    assert 'PAUSE_SENTINEL = Path("/var/lib/mei-mg-email/sender_blocked.pause")' in text
    assert 'systemctl", "is-active", "--quiet", WORKER_UNIT' in text
    assert "sender worker is active; refusing retention apply" in text


def test_retention_preserves_history_and_writes_suppression_before_company_delete():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "register_operational_suppression" in text
    assert "canonical_retention_maintenance" in text
    assert "DELETE FROM mei_email.empresas" in text
    assert "DELETE FROM mei_email.envios" not in text
    assert text.index("register_operational_suppression") < text.index("DELETE FROM mei_email.empresas")


def test_retention_matches_current_business_and_technical_exclusions():
    text = SCRIPT.read_text(encoding="utf-8")
    for marker in (
        "submitted",
        "delivered",
        "bounce_permanent",
        "opt_out",
        "situacao_cadastral <> 'ATIVA'",
        "is_valid_email_address",
        "filter_email_contabil",
        "filter_shared_email",
        "count(DISTINCT cnpj) > 2",
    ):
        assert marker in text


def test_retention_unit_is_manual_bounded_and_guarded():
    text = UNIT.read_text(encoding="utf-8")
    assert "Type=oneshot" in text
    assert "ConditionPathExists=/var/lib/mei-mg-email/sender_blocked.pause" in text
    assert "scripts/runtime_policy_guard.py" in text
    assert "operational_retention_maintenance.py --apply" in text
    assert "TimeoutStartSec=900" in text
    assert "[Timer]" not in text
