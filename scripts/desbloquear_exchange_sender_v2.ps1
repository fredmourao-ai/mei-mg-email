param(
    [Parameter(Mandatory=$true)][string]$AccessToken,
    [string]$SenderAddress = 'naoresponda@dev.shopvivaliz.com.br',
    [string]$Organization = 'contabilidademelo.onmicrosoft.com',
    [string]$AdminUpn = ''
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function ConvertFrom-Base64UrlJson {
    param([Parameter(Mandatory=$true)][string]$Value)
    $padded = $Value.Replace('-', '+').Replace('_', '/')
    switch ($padded.Length % 4) {
        2 { $padded += '==' }
        3 { $padded += '=' }
    }
    return ([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($padded))) | ConvertFrom-Json
}

$parts = $AccessToken.Split('.')
if ($parts.Count -ne 3) { throw 'EXCHANGE_TOKEN_INVALID: JWT esperado.' }
$claims = ConvertFrom-Base64UrlJson -Value $parts[1]
$aud = [string]$claims.aud
$exchangeAudiences = @('https://outlook.office365.com','https://outlook.office365.com/','00000002-0000-0ff1-ce00-000000000000')
if ($exchangeAudiences -notcontains $aud) {
    if ($aud -eq 'https://graph.microsoft.com' -or $aud -eq '00000003-0000-0000-c000-000000000000') {
        throw 'EXCHANGE_TOKEN_WRONG_AUDIENCE: token Microsoft Graph nao pode autenticar Exchange Online PowerShell. Gere para https://outlook.office365.com/.default.'
    }
    throw "EXCHANGE_TOKEN_WRONG_AUDIENCE: $aud"
}

if ($claims.exp) {
    $expiry = [DateTimeOffset]::FromUnixTimeSeconds([int64]$claims.exp)
    if ($expiry -le [DateTimeOffset]::UtcNow.AddMinutes(2)) { throw 'EXCHANGE_TOKEN_EXPIRED' }
}

if ($env:GITHUB_ACTIONS -eq 'true') { Write-Output "::add-mask::$AccessToken" }
Import-Module ExchangeOnlineManagement -ErrorAction Stop

$connect = @{
    AccessToken = $AccessToken
    ShowBanner = $false
    CommandName = @('Get-BlockedSenderAddress','Remove-BlockedSenderAddress')
}

$delegated = $null -ne $claims.PSObject.Properties['scp']
if ($delegated) {
    if ([string]::IsNullOrWhiteSpace($AdminUpn)) {
        foreach ($name in @('preferred_username','upn','unique_name')) {
            $p = $claims.PSObject.Properties[$name]
            if ($null -ne $p -and -not [string]::IsNullOrWhiteSpace([string]$p.Value)) { $AdminUpn = [string]$p.Value; break }
        }
    }
    if ([string]::IsNullOrWhiteSpace($AdminUpn)) { throw 'EXCHANGE_ADMIN_UPN_MISSING' }
    $connect['UserPrincipalName'] = $AdminUpn
} else {
    $connect['Organization'] = $Organization
}

$connected = $false
try {
    Connect-ExchangeOnline @connect
    $connected = $true
    Write-Host "EXCHANGE_CONNECTED sender=$SenderAddress"

    $blocked = Get-BlockedSenderAddress -SenderAddress $SenderAddress -ErrorAction SilentlyContinue
    if ($null -ne $blocked) {
        Write-Host "SENDER_BLOCKED_CONFIRMED sender=$SenderAddress"
        Remove-BlockedSenderAddress -SenderAddress $SenderAddress -Confirm:$false
        Write-Host "UNBLOCK_SUBMITTED sender=$SenderAddress"
    } else {
        Write-Host "SENDER_ALREADY_UNBLOCKED sender=$SenderAddress"
    }

    $deadline = [DateTimeOffset]::UtcNow.AddMinutes(5)
    do {
        Start-Sleep -Seconds 10
        $remaining = Get-BlockedSenderAddress -SenderAddress $SenderAddress -ErrorAction SilentlyContinue
        if ($null -eq $remaining) { break }
    } while ([DateTimeOffset]::UtcNow -lt $deadline)

    if ($null -ne $remaining) { throw 'EXCHANGE_UNBLOCK_NOT_CONFIRMED' }
    Write-Host "EXCHANGE_UNBLOCK_CONFIRMED sender=$SenderAddress"
} finally {
    if ($connected) { Disconnect-ExchangeOnline -Confirm:$false -ErrorAction SilentlyContinue }
}
