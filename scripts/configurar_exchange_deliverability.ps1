param(
    [string]$Sender = 'naoresponda@dev.shopvivaliz.com.br',
    [string]$Organization = 'contabilidademelo.onmicrosoft.com',
    [string]$AppId = '',
    [string]$CertificatePath = '',
    [string]$PrivateKeyPath = ''
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

if ([string]::IsNullOrWhiteSpace($AppId)) { throw 'EXCHANGE_APP_ID_MISSING: MICROSOFT_GRAPH_CLIENT_ID nao configurado.' }
if (-not (Test-Path -LiteralPath $CertificatePath -PathType Leaf)) { throw "EXCHANGE_CERT_MISSING: $CertificatePath" }
if (-not (Test-Path -LiteralPath $PrivateKeyPath -PathType Leaf)) { throw "EXCHANGE_PRIVATE_KEY_MISSING: $PrivateKeyPath" }

$SenderPattern = '^naoresponda@dev\.shopvivaliz\.com\.br$'
Import-Module ExchangeOnlineManagement -ErrorAction Stop
$certificate = [System.Security.Cryptography.X509Certificates.X509Certificate2]::CreateFromPemFile($CertificatePath, $PrivateKeyPath)
if (-not $certificate.HasPrivateKey) { throw 'EXCHANGE_CERT_PRIVATE_KEY_UNAVAILABLE' }

function Ensure-HeaderRule {
    param(
        [Parameter(Mandatory=$true)][string]$Name,
        [Parameter(Mandatory=$true)][string]$HeaderName,
        [Parameter(Mandatory=$true)][string]$HeaderValue
    )

    $existing = Get-TransportRule -Identity $Name -ErrorAction SilentlyContinue
    if ($null -eq $existing) {
        New-TransportRule `
            -Name $Name `
            -SenderAddressMatchesPatterns $SenderPattern `
            -SenderAddressLocation Header `
            -SetHeaderName $HeaderName `
            -SetHeaderValue $HeaderValue `
            -Mode Enforce | Out-Null
        Write-Host "CREATED=$Name"
    }
    else {
        Set-TransportRule `
            -Identity $Name `
            -SenderAddressMatchesPatterns $SenderPattern `
            -SenderAddressLocation Header `
            -SetHeaderName $HeaderName `
            -SetHeaderValue $HeaderValue `
            -Mode Enforce
        Write-Host "UPDATED=$Name"
    }

    $verified = Get-TransportRule -Identity $Name -ErrorAction Stop
    if ($verified.State -ne 'Enabled') { throw "TRANSPORT_RULE_NOT_ENABLED: $Name" }
    Write-Host "VERIFIED=$Name"
}

$connected = $false
try {
    Connect-ExchangeOnline `
        -AppId $AppId `
        -Certificate $certificate `
        -Organization $Organization `
        -ShowBanner:$false `
        -CommandName @('Get-TransportRule','New-TransportRule','Set-TransportRule')
    $connected = $true
    Write-Host "EXCHANGE_APP_ONLY_CONNECTED organization=$Organization"

    Ensure-HeaderRule `
        -Name 'ShopVivaliz MEI OneClick Unsubscribe' `
        -HeaderName 'List-Unsubscribe-Post' `
        -HeaderValue 'List-Unsubscribe=One-Click'

    Ensure-HeaderRule `
        -Name 'ShopVivaliz MEI Gmail Feedback ID' `
        -HeaderName 'Feedback-ID' `
        -HeaderValue 'meimg:marketing:contamelo:VivalizMEI'

    Write-Host "DELIVERABILITY_TRANSPORT_RULES_READY sender=$Sender"
}
finally {
    if ($connected) { Disconnect-ExchangeOnline -Confirm:$false -ErrorAction SilentlyContinue }
    if ($null -ne $certificate) { $certificate.Dispose() }
}
