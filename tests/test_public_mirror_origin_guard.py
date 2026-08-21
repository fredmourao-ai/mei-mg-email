from pathlib import Path

from worker.safe_entrypoint_v2 import (
    _disallowed_marketing_origin,
    _disallowed_mei_origin,
)


MIGRATION = Path("db/migrations/V048__reject_public_mirror_operator_origins.sql")


def test_historical_huggingface_operator_origin_is_rejected_pre_send():
    origin = "politica_importacao_operador_2026-08-13_huggingface_upsert"
    assert _disallowed_marketing_origin(origin)
    assert _disallowed_mei_origin(origin)


def test_public_base_is_never_marketing_opt_in():
    assert _disallowed_marketing_origin("base_publica_sem_opt_in")
    assert _disallowed_marketing_origin("base_publica_sem_opt_in_20260819")


def test_known_official_mei_verification_source_is_not_rejected():
    assert not _disallowed_mei_origin("receita_simples_opcao_mei")


def test_v048_closes_prefix_loophole_before_autoqueue_limit_helpers():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "create or replace function mei_email.is_independent_marketing_authorization" in sql
    assert "create or replace function mei_email.is_independent_mei_verification" in sql
    assert "not like 'politica_importacao_operador%'" in sql
    assert "not like 'base_publica%'" in sql
    assert "e.status::text in ('pendente', 'enviando', 'pending', 'processing')" in sql
    assert "terminal" not in sql.lower().split("update mei_email.envios", 1)[1].split("comment on function", 1)[0]
