import importlib.util
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "ingest_casa_dos_dados_daily",
    ROOT / "scripts" / "ingest_casa_dos_dados_daily.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return b'{"total":0,"cnpjs":[]}'


class FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_request_page_asks_for_complete_contact_result(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        return FakeResponse()

    monkeypatch.setattr(MODULE, "API_KEY", "test-key")
    monkeypatch.setattr(MODULE, "urlopen", fake_urlopen)

    MODULE.request_page({"limite": 1, "pagina": 1})

    query = parse_qs(urlparse(captured["url"]).query)
    assert query.get("tipo_resultado") == ["completo"]


def test_nonempty_search_without_contact_data_fails_closed(monkeypatch):
    monkeypatch.setattr(MODULE, "API_KEY", "test-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/test")
    monkeypatch.setattr(MODULE.psycopg, "connect", lambda *_a, **_k: FakeConnection())
    monkeypatch.setattr(
        MODULE,
        "request_page",
        lambda _payload: {
            "total": 1,
            "cnpjs": [
                {
                    "cnpj": "12345678000190",
                    "razao_social": "EMPRESA TESTE",
                    "situacao_cadastral": {"situacao_cadastral": "ATIVA"},
                }
            ],
        },
    )
    monkeypatch.setattr(MODULE, "upsert_companies", lambda _conn, _rows: (0, 0))

    with pytest.raises(RuntimeError, match="contato"):
        MODULE.main()
