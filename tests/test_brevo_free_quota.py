import importlib

import app.config as config_module


def _reload_settings(monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER", "brevo")
    monkeypatch.setenv("MAX_ENVIOS_POR_DIA", "10000")
    monkeypatch.setenv("META_ENVIOS_POR_DIA", "9950")
    module = importlib.reload(config_module)
    return module.Settings()


def test_brevo_free_hard_cap_never_exceeds_300(monkeypatch):
    settings = _reload_settings(monkeypatch)
    assert settings.max_envios_por_dia == 300


def test_brevo_free_default_target_keeps_headroom(monkeypatch):
    settings = _reload_settings(monkeypatch)
    assert settings.meta_envios_por_dia == 295
