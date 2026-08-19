from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_base_sync_commits_count_transaction_before_long_ingest_subprocess():
    source = (ROOT / "scripts" / "sincronizar_base_diaria.py").read_text(encoding="utf-8")
    normalized = " ".join(source.split())
    assert "rows_before = _count_companies(conn) conn.commit() ingest = subprocess.run" in normalized
    assert normalized.count("rows_before = _count_companies(conn) conn.commit()") >= 2
    assert "LOCK_ID = 14082026" in source
