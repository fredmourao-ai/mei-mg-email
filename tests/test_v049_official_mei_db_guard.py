from pathlib import Path

from worker.safe_entrypoint_v2 import _legacy_numeric_branch_cnpj


MIGRATION = Path("db/migrations/V049__enforce_official_mei_source_and_no_numeric_branch.sql")
QUEUE_MANAGER = Path("app/queue_manager.py")


def test_numeric_branch_guard_matches_impossible_mei_branch():
    assert _legacy_numeric_branch_cnpj("00000000084190")
    assert _legacy_numeric_branch_cnpj("00.000.000/0841-90")
    assert not _legacy_numeric_branch_cnpj("12345678000190")


def test_v049_requires_only_official_receita_mei_source_and_blocks_open_branch_work():
    sql = MIGRATION.read_text(encoding="utf-8").casefold()
    assert "= 'receita_simples_opcao_mei'" in sql
    assert "is_legacy_numeric_branch_cnpj" in sql
    assert "e.status::text in ('pendente', 'enviando', 'pending', 'processing')" in sql
    assert "submitted" in sql
    assert "delivered" in sql
    assert "bloqueio anti-replay" in sql


def test_autoqueue_still_excludes_terminal_history_before_first_limit():
    source = QUEUE_MANAGER.read_text(encoding="utf-8").casefold()
    base_start = source.index("with base as materialized")
    first_limit = source.index("limit %s", base_start)
    base = source[base_start:first_limit]
    assert "= 'receita_simples_opcao_mei'" in base
    assert "submitted" in base
    assert "enviado" in base
    assert "delivered" in base
    assert "bounced" in base
    assert "bounce_permanent" in base
