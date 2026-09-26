from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_autorepair_service_runs_throughput_supervisor_every_15m():
    service = (ROOT / "deploy/systemd/mei-mg-email-autorepair.service").read_text()
    timer = (ROOT / "deploy/systemd/mei-mg-email-autorepair.timer").read_text()
    assert "scripts/nonstop_supervisor_15m.py" in service
    assert "TimeoutStartSec=90" in service
    assert "OnUnitActiveSec=15min" in timer
    assert "Persistent=true" in timer


def test_supervisor_measures_real_throughput_and_keeps_safety_guards():
    src = (ROOT / "scripts/nonstop_supervisor_15m.py").read_text()
    assert "sender_blocked.pause" in src
    assert "worker_stopped_for_current_sender_block" in src
    assert "sent_24h" in src
    assert "sent_10m" in src
    assert "open_queue" in src
    assert "situacao_cadastral='ATIVA'" in src
    assert "is_valid_email_address" in src
    assert "position('contabil'" in src
    assert "vw_empresas_elegiveis" not in src
    assert "pg_locks" in src
    assert "pg_stat_activity" in src
    assert "repor_fila_automatica_isolada" in src
    assert "bounded_autoqueue_refill_added" in src
    assert "healthy_real_throughput" in src
    assert "degraded_eligibility_query_error" in src
    assert "unlink(" not in src
    assert "remove(" not in src
    assert "provider.send" not in src
    assert ("marketing_" + "autorizado = true") not in src.lower()
    assert "mei_verificado = true" not in src.lower()


def test_supervisor_uses_same_rolling_quota_ledger_as_worker():
    src = (ROOT / "scripts/nonstop_supervisor_15m.py").read_text()
    assert "envios_externos_cota" in src
    assert "quota_24h" in src
    assert "statement_timestamp() - interval '24 hours'" in src
    decision_tail = src.split("below_target =", 1)[1]
    assert 'before["quota_24h"]' in decision_tail
    assert 'after["quota_24h"]' in decision_tail


def test_supervisor_first_value_handles_dict_row_and_sequence():
    import importlib.util
    spec = importlib.util.spec_from_file_location("supervisor", ROOT / "scripts/nonstop_supervisor_15m.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    assert module._first_value({"to_regclass": "mei_email.envios_externos_cota"}) == "mei_email.envios_externos_cota"
    assert module._first_value((300,)) == 300


def test_supervisor_renders_api_unit_placeholders_before_install(monkeypatch, tmp_path):
    import importlib.util
    import subprocess

    spec = importlib.util.spec_from_file_location("supervisor_render", ROOT / "scripts/nonstop_supervisor_15m.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    app_dir = tmp_path / "app"
    venv_python = app_dir / ".venv" / "bin" / "python"
    venv_python.parent.mkdir(parents=True)
    venv_python.write_text("#!/bin/sh\n")

    source = tmp_path / "mei-mg-email-api.service.template"
    installed = tmp_path / "mei-mg-email-api.service"
    source.write_text(
        "[Service]\n"
        "User=__RUN_USER__\n"
        "WorkingDirectory=__APP_DIR__\n"
        "EnvironmentFile=__APP_DIR__/.env\n"
        "ExecStart=__PYTHON__ -m uvicorn app.main:app --host 127.0.0.1 --port 8010\n"
    )

    monkeypatch.setattr(module, "BASE_DIR", app_dir)
    monkeypatch.setattr(module, "API_UNIT_SOURCE", source)
    monkeypatch.setattr(module, "API_UNIT_INSTALLED", installed)
    monkeypatch.setattr(
        module,
        "_systemctl",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, "", ""),
    )

    result = {"actions": []}
    module._sync_api_unit(result)

    rendered = installed.read_text()
    assert "__APP_DIR__" not in rendered
    assert "__RUN_USER__" not in rendered
    assert "__PYTHON__" not in rendered
    assert f"WorkingDirectory={app_dir}" in rendered
    assert f"ExecStart={venv_python}" in rendered
    assert result["actions"] == ["api_unit_synced"]
