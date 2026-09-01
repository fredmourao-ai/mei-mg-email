from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_nonstop_supervisor_repairs_api_systemd_supervision():
    src = (ROOT / "scripts" / "nonstop_supervisor_15m.py").read_text(encoding="utf-8")
    assert 'API_UNIT = "mei-mg-email-api.service"' in src
    assert "api_health" in src
    assert "api_orphan_terminated" in src
    assert "api_restarted" in src
    assert '_systemctl("restart", API_UNIT' in src


def test_api_unit_restarts_after_clean_termination():
    unit = (ROOT / "deploy" / "systemd" / "mei-mg-email-api.service").read_text(encoding="utf-8")
    assert "Restart=always" in unit
