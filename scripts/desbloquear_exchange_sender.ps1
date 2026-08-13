param(
    [string]$SenderAddress = 'naoresponda@dev.shopvivaliz.com.br',
    [string]$Organization = 'contabilidademelo.onmicrosoft.com',
    [string]$AdminUpn = '',
    [string]$AccessToken = '',
    [switch]$RemovePauseOnSuccess,
    [string]$PauseFile = 'runtime/sender_blocked.pause'
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
    $bytes = [Convert]::FromBase64String($padded)
    $json = [Text.Encoding]::UTF8.GetString($bytes)
    return $json | ConvertFrom-Json
}

function Get-TokenClaims {
    param([Parameter(Mandatory=$true)][string]$Token)
    $parts = $Token.Split('.')
    if ($parts.Count -ne 3) {
        throw 'EXCHANGE_TOKEN_INVALID: token OAuth nao possui formato JWT esperado.'
    }
    return ConvertFrom-Base64UrlJson -Value $parts[1]
}

function Assert-ExchangeToken {
    param([Parameter(Mandatory=$true)][string]$Token)
    $claims = Get-TokenClaims -Token $Token
    $aud = [string]$claims.aud
    $allowedAudiences = @(
        'https://outlook.office365.com',
        'https://outlook.office365.com/',
        '00000002-0000-0ff1-ce00-000000000000'
    )
    if ($allowedAudiences -notcontains $aud) {
        if ($aud -eq 'https://graph.microsoft.com' -or $aud -eq '00000003-0000-0000-c000-000000000000') {
            throw 'EXCHANGE_TOKEN_WRONG_AUDIENCE: foi fornecido token do Microsoft Graph. Para Connect-ExchangeOnline, gere token para https://outlook.office365.com/.default.'
        }
        throw "EXCHANGE_TOKEN_WRONG_AUDIENCE: audience inesperada: $aud"
    }

    if ($claims.exp) {
        $expiry = [DateTimeOffset]::FromUnixTimeSeconds([int64]$claims.exp)
        if ($expiry -le [DateTimeOffset]::UtcNow.AddMinutes(2)) {
            throw "EXCHANGE_TOKEN_EXPIRED: expira em $($expiry.ToString('o'))"
        }
    }
    return $claims
}

if ([string]::IsNullOrWhiteSpace($AccessToken)) {
    $candidates = @(
        $env:EXCHANGE_ADMIN_ACCESS_TOKEN,
        $env:MICROSOFT_EXCHANGE_ADMIN_TOKEN,
        $env:MICROSOFT_GRAPH_ADMIN_TOKEN,
        $env:MICROSOFT_GRAPH_ACCESS_TOKEN
    ) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    if ($candidates.Count -gt 0) {
        $AccessToken = [string]$candidates[0]
    }
}

if ([string]::IsNullOrWhiteSpace($AccessToken)) {
    throw 'EXCHANGE_ADMIN_TOKEN_MISSING: configure o token em secret/variavel segura; nunca grave token no repositorio ou log.'
}

# Redundante ao masking do GitHub Secrets, mas evita exposicao acidental em Actions.
if ($env:GITHUB_ACTIONS -eq 'true') {
    Write-Output "::add-mask::$AccessToken"
}

$claims = Assert-ExchangeToken -Token $AccessToken

Import-Module ExchangeOnlineManagement -ErrorAction Stop

$connectArgs = @{
    AccessToken = $AccessToken
    ShowBanner = $false
    CommandName = @('Get-BlockedSenderAddress', 'Remove-BlockedSenderAddress')
}

$tokenUpn = ''
foreach ($claimName in @('preferred_username', 'upn', 'unique_name')) {
    $prop = $claims.PSObject.Properties[$claimName]
    if ($null -ne $prop -and -not [string]::IsNullOrWhiteSpace([string]$prop.Value)) {
        $tokenUpn = [string]$prop.Value
        break
    }
}

$hasDelegatedScopes = $null -ne $claims.PSObject.Properties['scp']
if ($hasDelegatedScopes) {
    if ([string]::IsNullOrWhiteSpace($AdminUpn)) { $AdminUpn = $tokenUpn }
    if ([string]::IsNullOrWhiteSpace($AdminUpn)) {
        throw 'EXCHANGE_ADMIN_UPN_MISSING: token delegado exige AdminUpn/EXCHANGE_ADMIN_UPN.'
    }
    $connectArgs['UserPrincipalName'] = $AdminUpn
}
else {
    if ([string]::IsNullOrWhiteSpace($Organization)) {
        throw 'EXCHANGE_ORGANIZATION_MISSING: token app-only exige dominio onmicrosoft.com da organizacao.'
    }
    $connectArgs['Organization'] = $Organization
}

try {
    Connect-ExchangeOnline @connectArgs
    Write-Host "EXCHANGE_CONNECTED sender=$SenderAddress"

    $blocked = Get-BlockedSenderAddress -SenderAddress $SenderAddress -ErrorAction SilentlyContinue
    if ($null -eq $blocked) {
        Write-Host "SENDER_ALREADY_UNBLOCKED sender=$SenderAddress"
    }
    else {
        $reason = [string]$blocked.Reason
        if ([string]::IsNullOrWhiteSpace($reason)) {
            Write-Host "SENDER_BLOCKED_CONFIRMED sender=$SenderAddress"
        }
        else {
            Write-Host "SENDER_BLOCKED_CONFIRMED sender=$SenderAddress reason=$reason"
        }

        Remove-BlockedSenderAddress -SenderAddress $SenderAddress -Confirm:$false
        Write-Host "UNBLOCK_SUBMITTED sender=$SenderAddress"
    }

    # A lista de Restricted entities deve deixar de retornar o remetente. A
    # propagacao completa do envio pode levar mais tempo na infraestrutura da Microsoft.
    $deadline = (Get-Date).ToUniversalTime().AddMinutes(5)
    do {
        Start-Sleep -Seconds 10
        $remaining = Get-BlockedSenderAddress -SenderAddress $SenderAddress -ErrorAction SilentlyContinue
        if ($null -eq $remaining) { break }
    } while ((Get-Date).ToUniversalTime() -lt $deadline)

    if ($null -ne $remaining) {
        throw "EXCHANGE_UNBLOCK_NOT_CONFIRMED: $SenderAddress ainda aparece em Restricted entities."
    }

    Write-Host "EXCHANGE_UNBLOCK_CONFIRMED sender=$SenderAddress"

    if ($RemovePauseOnSuccess) {
        $resolvedPause = Resolve-Path -LiteralPath $PauseFile -ErrorAction SilentlyContinue
        if ($null -ne $resolvedPause) {
            Remove-Item -LiteralPath $resolvedPause.Path -Force
            Write-Host "LOCAL_SENDER_PAUSE_REMOVED path=$($resolvedPause.Path)"
        }
        else {
            Write-Host "LOCAL_SENDER_PAUSE_NOT_PRESENT path=$PauseFile"
        }
    }
}
finally {
    Disconnect-ExchangeOnline -Confirm:$false -ErrorAction SilentlyContinue
}
