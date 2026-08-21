from pathlib import Path

from worker.safe_entrypoint_v2 import _legacy_numeric_branch_cnpj


MIGRATION = Path("db/migrations/V047__reject_legacy_numeric_mei_filiais.sql")


def test_legacy_numeric_branch_is_rejected():
    assert _legacy_numeric_branch_cnpj("02.307.635/0003-23") is True
    assert _legacy_numeric_branch_cnpj("02307635000323") is True


def test_legacy_numeric_matrix_is_not_rejected_by_branch_guard():
    assert _legacy_numeric_branch_cnpj("65.002.399/0001-95") is False


def test_alphanumeric_cnpj_is_not_inferred_from_legacy_suffix_rule():
    assert _legacy_numeric_branch_cnpj("00000000E08G12") is False


def test_v047_invalidates_verification_and_only_discards_open_rows():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "mei_verificado = false" in sql
    assert "invalidated_legacy_numeric_filial_mei_guard_2026-08-21" in sql
    assert "'descartado'::mei_email.status_envio" in sql
    assert "x.status::text in ('pendente', 'enviando', 'pending', 'processing')" in sql
    assert "submitted" not in sql.split("x.status::text in", 1)[1]
    assert "delivered" not in sql.split("x.status::text in", 1)[1]
