import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _settings_output(**values: object) -> tuple[str, str]:
    env = os.environ.copy()
    env.update({key: str(value) for key, value in values.items()})
    command = [
        sys.executable,
        "-c",
        "from app.config import settings; print(settings.max_envios_por_dia); print(settings.meta_envios_por_dia)",
    ]
    completed = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, check=True)
    return tuple(completed.stdout.splitlines())  # type: ignore[return-value]


def test_brevo_300_cap_is_global_runtime_contract():
    assert _settings_output(EMAIL_PROVIDER="brevo", MAX_ENVIOS_POR_DIA=10000, META_ENVIOS_POR_DIA=9950) == ("300", "300")
    assert _settings_output(EMAIL_PROVIDER="dryrun", MAX_ENVIOS_POR_DIA=10000, META_ENVIOS_POR_DIA=9950) == ("300", "300")


def test_lower_local_cap_is_respected():
    assert _settings_output(EMAIL_PROVIDER="brevo", MAX_ENVIOS_POR_DIA=200, META_ENVIOS_POR_DIA=300) == ("200", "200")


def test_active_config_has_no_exchange_quota_branch():
    source = (ROOT / "app" / "config.py").read_text(encoding="utf-8").casefold()
    assert "exchange_recipient_safety_reserve" not in source
    assert 'max_envios_por_dia", 10000' not in source
    assert 'meta_envios_por_dia", 9500' not in source


def test_legacy_named_dispatchers_are_safe_current_compatibility_wrappers():
    dispatch = (ROOT / "scripts" / "disparar_10000_mei_mg.py").read_text(encoding="utf-8").casefold()
    old_295 = (ROOT / "scripts" / "disparar_295_mei_mg.py").read_text(encoding="utf-8").casefold()
    for source in (dispatch, old_295):
        assert "microsoft graph" not in source
        assert "9950" not in source
        assert "9000" not in source
        assert "10000/24h" not in source
    assert "repor_fila_automatica" in dispatch


def test_exchange_auditor_is_retired_fail_closed():
    source = (ROOT / "scripts" / "auditar_exchange_10000.py").read_text(encoding="utf-8")
    assert "RETIRED_MICROSOFT_EXCHANGE_AUDITOR" in source
    assert "return 2" in source
    assert "MicrosoftGraphEmailProvider" not in source


def test_active_docs_do_not_restore_stale_quota_or_retired_policy():
    paths = (
        "README.md",
        ".env.example",
        "docs/fila-continua.md",
        "docs/contabilidade-melo-disparo.md",
        "ops/README.md",
        "deploy/systemd/gate-release.txt",
    )
    combined = "\n".join((ROOT / path).read_text(encoding="utf-8") for path in paths)
    for stale in (
        "META_ENVIOS_POR_DIA=9950",
        "QUEUE_MIN_PENDING=1000",
        "QUEUE_TARGET_PENDING=5000",
        "V022 marca o estoque existente",
        "V023 aplica a mesma politica",
        "aplicar V022/V023/V024",
        "V022/V023/V024 applied",
    ):
        assert stale not in combined, stale
