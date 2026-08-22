from pathlib import Path

from worker.worker_queue_first import _empresa_para_template

ROOT = Path(__file__).resolve().parents[1]


def test_worker_checkpoints_before_graph_side_effect():
    source = (ROOT / "worker" / "worker_queue_first.py").read_text(encoding="utf-8")
    checkpoint = source.index("_marcar_envio_em_transito(conn, envio[\"envio_id\"])")
    send = source.index("resultado = provider.send(", checkpoint)
    submitted = source.index('"submitted",', send)
    assert checkpoint < send < submitted
    assert "dispatch_started: aguardando resultado do Microsoft Graph" in source


def test_recovery_never_replays_explicit_uncertain_graph_checkpoint():
    migration = (
        ROOT
        / "db"
        / "migrations_archived_post_v020_20260821"
        / "V034__guard_uncertain_graph_dispatch_against_replay.sql"
    ).read_text(encoding="utf-8")
    normalized = " ".join(migration.split())
    assert "old.status::text = 'enviando'" in normalized
    assert "new.status::text = 'pendente'" in normalized
    assert "dispatch_started:%" in normalized
    assert "'submitted'::mei_email.status_envio" in normalized
    assert "envios_guard_uncertain_graph_dispatch" in normalized
    assert "lotes_guard_uncertain_graph_dispatch" in normalized
    assert "recuperado automaticamente apos worker interrompido" in normalized


def test_blank_trade_name_falls_back_without_inventing_company_name():
    rendered = _empresa_para_template(
        {"nome_fantasia": "", "razao_social": "EMPRESA TESTE LTDA"}
    )
    assert rendered["nome_fantasia"] == "EMPRESA TESTE LTDA"
    assert rendered["razao_social"] == "EMPRESA TESTE LTDA"


def test_missing_both_names_uses_neutral_greeting_fallback():
    rendered = _empresa_para_template({"nome_fantasia": None, "razao_social": None})
    assert rendered["nome_fantasia"] == "empreendedor(a)"
    assert rendered["razao_social"] == "empreendedor(a)"
