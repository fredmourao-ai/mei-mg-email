param(
    [string]$Sender = 'naoresponda@dev.shopvivaliz.com.br',
    [string]$Organization = 'contabilidademelo.onmicrosoft.com',
    [string]$AppId = $env:MICROSOFT_GRAPH_CLIENT_ID,
    [string]$CertificatePath = $(if ($env:MICROSOFT_GRAPH_CERT_PATH) { $env:MICROSOFT_GRAPH_CERT_PATH } else { '/home/ubuntu/.shopvivaliz/m365/graph-auth.crt' }),
    [string]$PrivateKeyPath = $(if ($env:MICROSOFT_GRAPH_KEY_PATH) { $env:MICROSOFT_GRAPH_KEY_PATH } else { '/home/ubuntu/.shopvivaliz/m365/graph-auth.key' })
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if ([string]::IsNullOrWhiteSpace($AppId)) { throw 'EXCHANGE_APP_ID_MISSING' }
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
    Write-Host "EXCHANGE_APP_ONLY_CONNECTED app_id=$AppId organization=$Organization"

    # RFC 8058 one-click header. O MIME do Graph ja envia List-Unsubscribe.
    Ensure-HeaderRule `
        -Name 'ShopVivaliz MEI OneClick Unsubscribe' `
        -HeaderName 'List-Unsubscribe-Post' `
        -HeaderValue 'List-Unsubscribe=One-Click'

    # Identificador estavel para feedback loop do Gmail.
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
