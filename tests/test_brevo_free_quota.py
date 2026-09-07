import importlib

import app.config as config_module


def _reload_settings(monkeypatch, *, maximum="10000", target="9950"):
    monkeypatch.setenv("EMAIL_PROVIDER", "brevo")
    monkeypatch.setenv("MAX_ENVIOS_POR_DIA", maximum)
    monkeypatch.setenv("META_ENVIOS_POR_DIA", target)
    module = importlib.reload(config_module)
    return module.Settings()


def test_brevo_free_hard_cap_never_exceeds_300(monkeypatch):
    settings = _reload_settings(monkeypatch)
    assert settings.max_envios_por_dia == 300


def test_brevo_approved_target_can_reach_hard_cap_300(monkeypatch):
    settings = _reload_settings(monkeypatch, maximum="300", target="300")
    assert settings.max_envios_por_dia == 300
    assert settings.meta_envios_por_dia == 300


def test_brevo_target_above_plan_is_clamped_to_300(monkeypatch):
    settings = _reload_settings(monkeypatch, maximum="999", target="999")
    assert settings.max_envios_por_dia == 300
    assert settings.meta_envios_por_dia == 300
