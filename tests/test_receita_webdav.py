from pathlib import Path

import pytest

from scripts import receita_webdav as receita


SHARE_URL = "https://arquivos.receitafederal.gov.br/index.php/s/TwY6Wd9h4aQ6DdP?dir=/"


def _entry(name: str, size: int = 100, is_dir: bool = False):
    return receita.DavEntry(name=name, href=f"/public.php/webdav/2026-08/{name}", size=size, is_dir=is_dir)


def test_parse_public_share_url():
    token, directory, webdav = receita.parse_share_url(SHARE_URL)
    assert token == "TwY6Wd9h4aQ6DdP"
    assert directory == ""
    assert webdav == "https://arquivos.receitafederal.gov.br/public.php/webdav"


def test_select_latest_competence_ignores_non_month_directories():
    entries = [
        receita.DavEntry("2026-07", "/2026-07/", 0, True),
        receita.DavEntry("2026-08", "/2026-08/", 0, True),
        receita.DavEntry("README", "/README/", 0, True),
    ]
    assert receita.select_latest_competence(entries) == "2026-08"


def test_manifest_requires_exactly_ten_establishment_archives():
    entries = [_entry(f"Estabelecimentos{i}.zip") for i in range(10)]
    manifest = receita.build_manifest("2026-08", entries, "https://host/public.php/webdav/2026-08")
    assert manifest.competence == "2026-08"
    assert [item.name for item in manifest.files] == [f"Estabelecimentos{i}.zip" for i in range(10)]


def test_manifest_fails_closed_when_one_archive_is_missing():
    entries = [_entry(f"Estabelecimentos{i}.zip") for i in range(10) if i != 7]
    with pytest.raises(RuntimeError, match="Estabelecimentos7.zip"):
        receita.build_manifest("2026-08", entries, "https://host/public.php/webdav/2026-08")


def test_manifest_rejects_zero_sized_archive():
    entries = [_entry(f"Estabelecimentos{i}.zip", size=0 if i == 4 else 100) for i in range(10)]
    with pytest.raises(RuntimeError, match="Estabelecimentos4.zip"):
        receita.build_manifest("2026-08", entries, "https://host/public.php/webdav/2026-08")


def _row(*, status="02", uf="SP", email="empresa@example.com"):
    values = [""] * 28
    values[0] = "12345678"
    values[1] = "0001"
    values[2] = "90"
    values[4] = "EMPRESA TESTE"
    values[5] = status
    values[10] = "20260901"
    values[19] = uf
    values[21] = "11"
    values[22] = "999999999"
    values[27] = email
    return values


def test_canonical_row_filter_keeps_non_mg_company():
    parsed = receita.parse_establishment_row(_row(uf="SP"))
    assert parsed is not None
    assert parsed["uf"] == "SP"
    assert parsed["situacao_cadastral"] == "ATIVA"


def test_canonical_row_filter_rejects_inactive_and_contabil_email():
    assert receita.parse_establishment_row(_row(status="08")) is None
    assert receita.parse_establishment_row(_row(email="financeiro@contabilidade.com.br")) is None


def test_upsert_sql_has_no_mg_gate_and_does_not_touch_stateful_columns():
    sql = receita.build_upsert_sql().casefold()
    compact = sql.replace(" ", "")
    assert "uf='mg'" not in compact
    assert "uf=\'mg\'" not in compact
    update_clause = sql.split("do update set", 1)[1]
    for forbidden in ("opt_out", "enviado", "marketing_autorizado", "provavel_terceiro"):
        assert forbidden not in update_clause


def test_disk_guard_requires_archive_plus_reserve(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(receita.shutil, "disk_usage", lambda _path: type("D", (), {"free": 149})())
    with pytest.raises(RuntimeError, match="espaco"):
        receita.ensure_disk_headroom(tmp_path, remote_size=100, reserve_bytes=50)
    monkeypatch.setattr(receita.shutil, "disk_usage", lambda _path: type("D", (), {"free": 150})())
    receita.ensure_disk_headroom(tmp_path, remote_size=100, reserve_bytes=50)
