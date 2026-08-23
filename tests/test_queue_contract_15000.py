from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_all_replenishment_paths_use_15k_buffer_and_200_batch():
    config = (ROOT / "app" / "config.py").read_text(encoding="utf-8")
    manager = (ROOT / "app" / "queue_manager.py").read_text(encoding="utf-8")
    replenisher = (ROOT / "scripts" / "queue_replenisher.py").read_text(encoding="utf-8")

    assert 'QUEUE_MIN_PENDING", "14800"' in config
    assert 'QUEUE_TARGET_PENDING", "15000"' in config
    assert "AUTOQUEUE_REFILL_BATCH_SIZE = 200" in manager
    assert "TARGET = 15000" in replenisher
    assert "MINIMUM = 14800" in replenisher
    assert "BATCH = 200" in replenisher
