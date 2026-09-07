from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER_UNIT = ROOT / "deploy" / "systemd" / "mei-mg-email-worker.service"
PREFLIGHT = ROOT / "scripts" / "runtime_sender_preflight.py"
TEST_SCRIPT = ROOT / "scripts" / "enviar_teste_brevo.py"
MATERIALIZER = ROOT / "scripts" / "materialize_brevo_runtime_secret.py"
ENV_EXAMPLE = ROOT / ".env.example"
README = ROOT / "README.md"
DISPATCH_DOC = ROOT / "docs" / "contabilidade-melo-disparo.md"
AGENTS = ROOT / "AGENTS.md"


def test_worker_unit_is_brevo_specific():
    text = WORKER_UNIT.read_text(encoding="utf-8")
    assert "Brevo Free" in text
    assert "Microsoft Graph" not in text


def test_preflight_fail_closed_requires_brevo_secret_sender_and_cap():
    source = PREFLIGHT.read_text(encoding="utf-8")
    assert 'EMAIL_PROVIDER' in source
    assert 'BREVO_API_KEY' in source
    assert 'atendimento@shopvivaliz.com.br' in source
    assert 'naoresponda@dev.shopvivaliz.com.br' not in source
    assert 'MAX_ENVIOS_POR_DIA' in source
    assert 'META_ENVIOS_POR_DIA' in source
    assert '> 300' in source


def test_materializer_and_active_docs_use_validated_brevo_sender():
    for path in (MATERIALIZER, ENV_EXAMPLE, README, DISPATCH_DOC):
        source = path.read_text(encoding="utf-8")
        assert "atendimento@shopvivaliz.com.br" in source, path
    materializer = MATERIALIZER.read_text(encoding="utf-8")
    assert "Contabilidade Melo <atendimento@shopvivaliz.com.br>" in materializer


def test_controlled_test_requires_real_delivery_and_records_quota():
    assert TEST_SCRIPT.exists()
    source = TEST_SCRIPT.read_text(encoding="utf-8")
    assert "brevo_controlled_test" in source
    assert '"delivered"' in source
    assert "envios_externos_cota" in source
    assert "BREVO_TEST_DELIVERED" in source
    assert "BREVO_TEST_TIMEOUT_SECONDS" in source
    assert "messageId" in source


def test_docs_describe_brevo_as_current_provider_without_changing_filters():
    readme = README.read_text(encoding="utf-8")
    agents = AGENTS.read_text(encoding="utf-8")
    assert "Brevo" in readme
    assert "300" in readme
    assert "Provedor exclusivo: **Microsoft Graph" not in readme
    for marker in (
        "empresa com situacao cadastral diferente de ATIVA",
        "email contendo a palavra `contabil`",
        "email compartilhado por mais de 2 cadastros",
        "destinatario/CNPJ ja enviado ou ja enfileirado",
        "MG e apenas prioridade de ordenacao, nunca filtro de elegibilidade",
    ):
        assert marker in agents
