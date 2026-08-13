param(
    [string]$SenderAddress = 'naoresponda@dev.shopvivaliz.com.br',
    [string]$Organization = 'contabilidademelo.onmicrosoft.com',
    [string]$AppId = '',
    [string]$CertificatePath = '',
    [string]$PrivateKeyPath = '',
    [switch]$ConfirmUnblock
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$DotEnvPath = Join-Path $RepoRoot '.env'

function Get-ConfigValue {
    param(
        [Parameter(Mandatory=$true)][string]$Name,
        [string]$CurrentValue = '',
        [string]$DefaultValue = ''
    )
    if (-not [string]::IsNullOrWhiteSpace($CurrentValue)) { return $CurrentValue }
    $fromEnv = [Environment]::GetEnvironmentVariable($Name)
    if (-not [string]::IsNullOrWhiteSpace($fromEnv)) { return $fromEnv }
    if (Test-Path -LiteralPath $DotEnvPath -PathType Leaf) {
        $prefix = "$Name="
        foreach ($line in Get-Content -LiteralPath $DotEnvPath) {
            if ($line.StartsWith($prefix, [System.StringComparison]::Ordinal)) {
                $value = $line.Substring($prefix.Length).Trim()
                if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
                    $value = $value.Substring(1, $value.Length - 2)
                }
                return $value
            }
        }
    }
    return $DefaultValue
}

$AppId = Get-ConfigValue -Name 'MICROSOFT_GRAPH_CLIENT_ID' -CurrentValue $AppId
$CertificatePath = Get-ConfigValue -Name 'MICROSOFT_GRAPH_CERT_PATH' -CurrentValue $CertificatePath -DefaultValue '/home/ubuntu/.shopvivaliz/m365/graph-auth.crt'
$PrivateKeyPath = Get-ConfigValue -Name 'MICROSOFT_GRAPH_KEY_PATH' -CurrentValue $PrivateKeyPath -DefaultValue '/home/ubuntu/.shopvivaliz/m365/graph-auth.key'

if ([string]::IsNullOrWhiteSpace($AppId)) {
    throw 'EXCHANGE_APP_ID_MISSING: MICROSOFT_GRAPH_CLIENT_ID nao configurado no ambiente nem no .env.'
}
if (-not (Test-Path -LiteralPath $CertificatePath -PathType Leaf)) {
    throw "EXCHANGE_CERT_MISSING: $CertificatePath"
}
if (-not (Test-Path -LiteralPath $PrivateKeyPath -PathType Leaf)) {
    throw "EXCHANGE_PRIVATE_KEY_MISSING: $PrivateKeyPath"
}

Import-Module ExchangeOnlineManagement -ErrorAction Stop
$certificate = [System.Security.Cryptography.X509Certificates.X509Certificate2]::CreateFromPemFile($CertificatePath, $PrivateKeyPath)
if (-not $certificate.HasPrivateKey) { throw 'EXCHANGE_CERT_PRIVATE_KEY_UNAVAILABLE' }

$connected = $false
try {
    Connect-ExchangeOnline `
        -AppId $AppId `
        -Certificate $certificate `
        -Organization $Organization `
        -ShowBanner:$false `
        -CommandName @('Get-BlockedSenderAddress','Remove-BlockedSenderAddress')
    $connected = $true
    Write-Host "EXCHANGE_APP_ONLY_CONNECTED organization=$Organization"

    $blocked = Get-BlockedSenderAddress -SenderAddress $SenderAddress -ErrorAction SilentlyContinue
    if ($null -eq $blocked) {
        Write-Host "EXCHANGE_SENDER_NOT_BLOCKED sender=$SenderAddress"
        Write-Host 'WORKER_RESUME_ALLOWED=false reason=controlled_test_still_required'
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
    if ($connected) { Disconnect-ExchangeOnline -Confirm:$false -ErrorAction SilentlyContinue }
    if ($null -ne $certificate) { $certificate.Dispose() }
}
