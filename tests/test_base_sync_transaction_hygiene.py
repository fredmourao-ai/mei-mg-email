from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def _section(src: str, start: str, end: str) -> str:
    return src.split(start, 1)[1].split(end, 1)[0]

def test_base_sync_commits_before_each_long_ingest_subprocess():
    source = (ROOT / "scripts" / "sincronizar_base_diaria.py").read_text(encoding="utf-8")
    for start, end in (("def sync_casa_dos_dados", "def sync_huggingface_fallback"), ("def sync_huggingface_fallback", "def main")):
        body = _section(source, start, end)
        count = body.index("rows_before = _count_companies(conn)")
        commit = body.index("conn.commit()", count)
        ingest = body.index("subprocess.run", commit)
        assert count < commit < ingest
    assert "LOCK_ID = 14082026" in source
