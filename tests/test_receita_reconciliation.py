from scripts import receita_webdav as receita


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


def test_classification_preserves_inactive_state_for_existing_reconciliation():
    row = receita.classify_establishment_row(_row(status="08", email="empresa@example.com"))
    assert row is not None
    assert row["situacao_cadastral"] == "BAIXADA"
    assert row["eligible"] is False


def test_active_invalid_or_contabil_email_becomes_ineligible_with_null_email():
    invalid = receita.classify_establishment_row(_row(status="02", email="sem-arroba"))
    contabil = receita.classify_establishment_row(_row(status="02", email="fiscal@contabilidade.com.br"))
    assert invalid is not None and invalid["situacao_cadastral"] == "ATIVA"
    assert contabil is not None and contabil["situacao_cadastral"] == "ATIVA"
    assert invalid["eligible"] is False and invalid["email"] is None
    assert contabil["eligible"] is False and contabil["email"] is None


def test_eligible_parser_remains_canonical_wrapper():
    assert receita.parse_establishment_row(_row(status="08")) is None
    assert receita.parse_establishment_row(_row(status="02", email="fiscal@contabilidade.com.br")) is None
    eligible = receita.parse_establishment_row(_row(status="02", uf="RJ"))
    assert eligible is not None
    assert eligible["uf"] == "RJ"


def test_upsert_skips_unchanged_conflicts_to_avoid_wal_amplification():
    sql = receita.build_upsert_sql().casefold()
    conflict = sql.split("on conflict", 1)[1]
    assert "do update" in conflict
    assert "where" in conflict
    assert "is distinct from" in conflict


def test_existing_ineligible_reconciliation_is_update_only_and_state_safe():
    sql = receita.build_reconcile_existing_sql().casefold()
    assert "update mei_email.empresas" in sql
    assert "insert into mei_email.empresas" not in sql
    assert "situacao_cadastral" in sql
    assert "email = case" in sql
    assert "then null" in sql
    for forbidden in ("opt_out", "enviado", "marketing_autorizado", "provavel_terceiro"):
        assert forbidden not in sql


def test_existing_cnpj_bloom_has_no_false_negatives_for_added_values():
    bloom = receita.ExistingCnpjBloom(bytes_size=1024, hashes=4)
    values = ["12345678000190", "98765432000110", "A2345678000190"]
    for value in values:
        bloom.add(value)
    assert all(value in bloom for value in values)
    assert len(bloom.bits) == 1024
