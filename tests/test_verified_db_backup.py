from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_verified_backup_timer_is_daily_persistent_and_bounded():
    timer = (ROOT / "deploy/systemd/mei-mg-email-db-backup.timer").read_text()

    assert "OnCalendar=*-*-* 04:30:00 UTC" in timer
    assert "RandomizedDelaySec=2m" in timer
    assert "Persistent=true" in timer


def test_verified_backup_script_checks_dump_remote_integrity_and_weekly_retention():
    script = (ROOT / "scripts/verified-db-backup-oci.sh").read_text()

    assert "pg_dump" in script
    assert "pg_restore -l" in script
    assert "sha256sum" in script
    assert "mei_mg_email-latest.dump" in script
    assert "mei_mg_email-weekly.dump" in script
    assert "date -u +%u" in script
    assert "os object head" in script
    assert "os object get" in script
    assert "cmp -s" in script
    assert "backup_verified=" in script


def test_backup_runtime_is_versioned_and_installer_replaces_legacy_weekly_timer():
    service = (ROOT / "deploy/systemd/mei-mg-email-db-backup.service").read_text()
    installer = (ROOT / "scripts/instalar_monitoramento_vm.sh").read_text()

    assert "verified-db-backup-oci.sh" in service
    assert "mei-mg-email-db-backup.service" in installer
    assert "mei-mg-email-db-backup.timer" in installer
    assert "systemctl disable --now shopvivaliz-db-backup.timer" in installer
    assert "systemctl enable --now mei-mg-email-db-backup.timer" in installer
