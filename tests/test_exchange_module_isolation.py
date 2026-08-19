from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "desbloquear_exchange_app_cert.ps1"


def test_exchange_probe_isolates_conflicting_packagemanagement_module_path():
    text = SCRIPT.read_text(encoding="utf-8")

    assert "$originalPSModulePath = $env:PSModulePath" in text
    assert "Get-Module -ListAvailable -Name ExchangeOnlineManagement" in text
    assert "$env:PSModulePath = [string]::Join" in text
    assert "Remove-Module -Name PackageManagement,PowerShellGet" in text
    assert "Import-Module -Name $exchangeManifest -Force -ErrorAction Stop" in text
    assert "$env:PSModulePath = $originalPSModulePath" in text


def test_exchange_probe_remains_fail_closed_without_explicit_unblock_confirmation():
    text = SCRIPT.read_text(encoding="utf-8")

    assert "if (-not $ConfirmUnblock)" in text
    assert "EXCHANGE_UNBLOCK_NOT_EXECUTED confirm_required=true" in text
    assert "Remove-BlockedSenderAddress" in text
    assert "WORKER_RESUME_ALLOWED=false" in text
