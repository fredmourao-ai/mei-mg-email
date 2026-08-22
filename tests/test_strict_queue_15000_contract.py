from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_strict_queue_contract_and_15000_buffer():
    q = (ROOT / "app" / "queue_manager.py").read_text(encoding="utf-8")
    cfg = (ROOT / "app" / "config.py").read_text(encoding="utf-8")
    for token in (
        "where e.tipo_regime = 'MEI'",
        "and e.uf = 'MG'",
        "and e.marketing_autorizado = true",
        "and e.mei_verificado = true",
        "receita_simples_opcao_mei",
    ):
        assert token in q
    assert "AUTOQUEUE_LOT_SIZE = 200" in q
    assert "AUTOQUEUE_REFILL_BATCH_SIZE = 200" in q
    assert 'QUEUE_MIN_PENDING", "14800"' in cfg
    assert 'QUEUE_TARGET_PENDING", "15000"' in cfg


def test_external_replenisher_exists_and_uses_strict_manager():
    p = ROOT / "scripts" / "queue_replenisher.py"
    assert p.exists()
    src = p.read_text(encoding="utf-8")
    assert "repor_fila_automatica" in src
    assert "queue_manager" in src
