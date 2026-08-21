from pathlib import Path

from worker.safe_entrypoint_v2 import (
    OFFICIAL_MEI_VERIFICATION_ORIGINS,
    _disallowed_marketing_origin,
    _disallowed_mei_origin,
)


MIGRATION = Path("db/migrations/V048__reject_public_mirror_operator_origins.sql")
QUEUE_MANAGER = Path("app/queue_manager.py")


def test_historical_huggingface_operator_origin_is_rejected_pre_send():
    origin = "politica_importacao_operador_2026-08-13_huggingface_upsert"
    assert _disallowed_marketing_origin(origin)
    assert _disallowed_mei_origin(origin)


def test_public_base_is_never_marketing_opt_in():
    assert _disallowed_marketing_origin("base_publica_sem_opt_in")
    assert _disallowed_marketing_origin("base_publica_sem_opt_in_20260819")


def test_only_official_mei_verification_source_is_allowed_pre_send():
    assert OFFICIAL_MEI_VERIFICATION_ORIGINS == {"receita_simples_opcao_mei"}
    assert not _disallowed_mei_origin("receita_simples_opcao_mei")
    assert not _disallowed_mei_origin(" Receita_Simples_Opcao_Mei ")
    assert _disallowed_mei_origin("manual_review_mei")
    assert _disallowed_mei_origin("legacy_import_verified")
    assert _disallowed_mei_origin("")


def test_v048_closes_prefix_loophole_before_autoqueue_limit_helpers():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "create or replace function mei_email.is_independent_marketing_authorization" in sql
    assert "create or replace function mei_email.is_independent_mei_verification" in sql
    assert "not like 'politica_importacao_operador%'" in sql
    assert "not like 'base_publica%'" in sql
    assert "e.status::text in ('pendente', 'enviando', 'pending', 'processing')" in sql
    open_filter = sql.split("e.status::text in", 1)[1].split(");", 1)[0]
    assert "submitted" not in open_filter
    assert "enviado" not in open_filter
    assert "delivered" not in open_filter


def test_autoqueue_rejects_public_operator_prefixes_and_requires_official_mei_before_first_limit():
    source = QUEUE_MANAGER.read_text(encoding="utf-8").casefold()
    base_start = source.index("with base as materialized")
    first_limit = source.index("limit %s", base_start)
    base = source[base_start:first_limit]

    assert "not like 'politica_importacao_operador%%'" in base
    assert "not like 'base_publica%%'" in base
    assert "not like 'nao_verificado%%'" in base
    assert "not like 'legacy_operator_verification_rejected%%'" in base
    assert "= 'receita_simples_opcao_mei'" in base
    assert "submitted" in base
    assert "enviado" in base
    assert "delivered" in base
