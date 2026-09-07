from scripts import sincronizar_base_diaria as sync
from scripts.receita_webdav import ImportStats, RemoteZip, SnapshotManifest


def _manifest(month="2026-08"):
    return SnapshotManifest(
        competence=month,
        files=tuple(RemoteZip(f"Estabelecimentos{i}.zip", f"https://host/{i}.zip", 100) for i in range(10)),
        token="public-token",
        source_url="https://arquivos.receitafederal.gov.br/index.php/s/public?dir=/",
    )


def test_default_source_is_receita_webdav():
    assert sync.DAILY_SOURCE == "receita_webdav"
    assert sync.SOURCE_NAME == "receita_federal_webdav"


def test_receita_same_revision_records_no_change_without_import(monkeypatch):
    manifest = _manifest()
    monkeypatch.setattr(sync.receita_webdav, "discover_latest_snapshot", lambda: manifest)
    monkeypatch.setattr(sync, "_previous_successful_revision", lambda _c, _r: "receita:2026-08")
    called = {"import": False, "finish": None}
    monkeypatch.setattr(sync.receita_webdav, "import_snapshot", lambda *_a, **_k: called.__setitem__("import", True))
    monkeypatch.setattr(sync, "finish_run", lambda _c, _r, status, **fields: called.__setitem__("finish", (status, fields)))

    assert sync.sync_receita_webdav(object(), 10) == 0
    assert called["import"] is False
    assert called["finish"][0] == "no_change"
    assert called["finish"][1]["source_revision"] == "receita:2026-08"


def test_receita_new_revision_imports_and_records_success(monkeypatch):
    manifest = _manifest("2026-09")
    monkeypatch.setattr(sync.receita_webdav, "discover_latest_snapshot", lambda: manifest)
    monkeypatch.setattr(sync, "_previous_successful_revision", lambda _c, _r: "receita:2026-08")
    counts = iter([100, 112])
    monkeypatch.setattr(sync, "_count_companies", lambda _c: next(counts))
    monkeypatch.setattr(
        sync.receita_webdav,
        "import_snapshot",
        lambda *_a, **_k: ImportStats(files_processed=10, rows_read=200, eligible=20, upserted=20),
    )
    captured = {}
    monkeypatch.setattr(sync, "finish_run", lambda _c, _r, status, **fields: captured.update(status=status, **fields))

    assert sync.sync_receita_webdav(object(), 11) == 0
    assert captured["status"] == "success"
    assert captured["source_revision"] == "receita:2026-09"
    assert captured["rows_before"] == 100
    assert captured["rows_after"] == 112
    assert captured["details"]["import"]["files_processed"] == 10
