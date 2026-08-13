param(
    [string]$SenderAddress = 'naoresponda@dev.shopvivaliz.com.br',
    [string]$Organization = 'contabilidademelo.onmicrosoft.com',
    [string]$AppId = $env:MICROSOFT_GRAPH_CLIENT_ID,
    [string]$CertificatePath = $(if ($env:MICROSOFT_GRAPH_CERT_PATH) { $env:MICROSOFT_GRAPH_CERT_PATH } else { '/home/ubuntu/.shopvivaliz/m365/graph-auth.crt' }),
    [string]$PrivateKeyPath = $(if ($env:MICROSOFT_GRAPH_KEY_PATH) { $env:MICROSOFT_GRAPH_KEY_PATH } else { '/home/ubuntu/.shopvivaliz/m365/graph-auth.key' }),
    [switch]$ConfirmUnblock
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if ([string]::IsNullOrWhiteSpace($AppId)) {
    throw 'EXCHANGE_APP_ID_MISSING: MICROSOFT_GRAPH_CLIENT_ID nao configurado.'
}
if (-not (Test-Path -LiteralPath $CertificatePath -PathType Leaf)) {
    throw "EXCHANGE_CERT_MISSING: $CertificatePath"
}
if (-not (Test-Path -LiteralPath $PrivateKeyPath -PathType Leaf)) {
    throw "EXCHANGE_PRIVATE_KEY_MISSING: $PrivateKeyPath"
}

Import-Module ExchangeOnlineManagement -ErrorAction Stop

$certificate = [System.Security.Cryptography.X509Certificates.X509Certificate2]::CreateFromPemFile(
    $CertificatePath,
    $PrivateKeyPath
)
if (-not $certificate.HasPrivateKey) {
    throw 'EXCHANGE_CERT_PRIVATE_KEY_UNAVAILABLE'
}

$connected = $false
try {
    Connect-ExchangeOnline `
        -AppId $AppId `
        -Certificate $certificate `
        -Organization $Organization `
        -ShowBanner:$false `
        -CommandName @('Get-BlockedSenderAddress','Remove-BlockedSenderAddress')
    $connected = $true
    Write-Host "EXCHANGE_APP_ONLY_CONNECTED app_id=$AppId organization=$Organization"

    $blocked = Get-BlockedSenderAddress -SenderAddress $SenderAddress -ErrorAction SilentlyContinue
    if ($null -eq $blocked) {
        Write-Host "EXCHANGE_SENDER_NOT_BLOCKED sender=$SenderAddress"
        exit 0
    }

    $reason = [string]$blocked.Reason
    Write-Host "EXCHANGE_SENDER_BLOCKED sender=$SenderAddress reason=$reason"

    if (-not $ConfirmUnblock) {
        Write-Host 'EXCHANGE_UNBLOCK_NOT_EXECUTED confirm_required=true'
        exit 2
    }

    Remove-BlockedSenderAddress `
        -SenderAddress $SenderAddress `
        -Reason 'Authorized recovery after AS(42004); worker remains fail-closed until verification.'
    Write-Host "EXCHANGE_UNBLOCK_SUBMITTED sender=$SenderAddress"

    $deadline = [DateTimeOffset]::UtcNow.AddMinutes(5)
    $remaining = $blocked
    do {
        Start-Sleep -Seconds 10
        $remaining = Get-BlockedSenderAddress -SenderAddress $SenderAddress -ErrorAction SilentlyContinue
        if ($null -eq $remaining) { break }
    } while ([DateTimeOffset]::UtcNow -lt $deadline)

    if ($null -ne $remaining) {
        throw "EXCHANGE_UNBLOCK_NOT_CONFIRMED: $SenderAddress continua em Restricted entities."
    }

    Write-Host "EXCHANGE_UNBLOCK_CONFIRMED sender=$SenderAddress"
    Write-Host 'WORKER_RESUME_ALLOWED=false reason=propagation_and_controlled_test_required'
}
finally {
    if ($connected) {
        Disconnect-ExchangeOnline -Confirm:$false -ErrorAction SilentlyContinue
    }
    if ($null -ne $certificate) {
        $certificate.Dispose()
    }
}
