import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "ingest_from_huggingface",
    ROOT / "scripts" / "ingest_from_huggingface.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class FakeDuckDB:
    def __init__(self):
        self.calls = 0

    def execute(self, query):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("HTTP GET error (HTTP 503 Service Unavailable)")
        return "cursor-ok"


def test_transient_http_503_is_retried_before_failing_lot():
    conn = FakeDuckDB()
    result = MODULE.execute_parquet_query_with_retry(
        conn,
        "select * from source",
        attempts=3,
        base_delay_seconds=0,
    )
    assert result == "cursor-ok"
    assert conn.calls == 2


def test_non_transient_source_error_is_not_retried():
    class BrokenDuckDB:
        def __init__(self):
            self.calls = 0

        def execute(self, query):
            self.calls += 1
            raise ValueError("schema mismatch")

    conn = BrokenDuckDB()
    try:
        MODULE.execute_parquet_query_with_retry(
            conn,
            "select * from source",
            attempts=3,
            base_delay_seconds=0,
        )
    except ValueError as exc:
        assert "schema mismatch" in str(exc)
    else:
        raise AssertionError("expected ValueError")
    assert conn.calls == 1


def test_huggingface_parquet_url_is_bound_not_interpolated_into_sql():
    source = (ROOT / "scripts" / "ingest_from_huggingface.py").read_text(encoding="utf-8")
    query_block = source.split("query =", 1)[1].split("cursor =", 1)[0]
    assert "read_parquet(?)" in query_block
    assert "{parquet_url}" not in query_block
    assert "parameters=(parquet_url,)" in source
