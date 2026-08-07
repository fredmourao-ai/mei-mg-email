param(
    [Parameter(Mandatory=$true)][string]$TenantId,
    [Parameter(Mandatory=$true)][string]$ClientId,
    [Parameter(Mandatory=$true)][string]$Thumbprint
)

$ErrorActionPreference = 'Stop'

function ConvertTo-Base64Url([byte[]]$Bytes) {
    [Convert]::ToBase64String($Bytes).TrimEnd('=').Replace('+','-').Replace('/','_')
}

function ConvertTextTo-Base64Url([string]$Text) {
    ConvertTo-Base64Url ([Text.Encoding]::UTF8.GetBytes($Text))
}

$normalized = ($Thumbprint -replace '\s','').ToUpperInvariant()
$cert = Get-ChildItem -Path Cert:\CurrentUser\My -ErrorAction Stop |
    Where-Object { $_.Thumbprint -eq $normalized -and $_.HasPrivateKey } |
    Select-Object -First 1

if (-not $cert) {
    throw "Certificate with private key not found in CurrentUser\\My: $normalized"
}
if ($cert.NotAfter -le (Get-Date).AddDays(7)) {
    throw "Certificate is expired or too close to expiration: $($cert.NotAfter.ToString('o'))"
}

$now = [DateTimeOffset]::UtcNow
$aud = "https://login.microsoftonline.com/$TenantId/oauth2/v2.0/token"
$header = [ordered]@{
    alg = 'RS256'
    typ = 'JWT'
    x5t = (ConvertTo-Base64Url $cert.GetCertHash())
}
$payload = [ordered]@{
    aud = $aud
    iss = $ClientId
    sub = $ClientId
    jti = [Guid]::NewGuid().ToString()
    nbf = $now.AddMinutes(-1).ToUnixTimeSeconds()
    exp = $now.AddMinutes(8).ToUnixTimeSeconds()
}

$headerPart = ConvertTextTo-Base64Url (($header | ConvertTo-Json -Compress))
$payloadPart = ConvertTextTo-Base64Url (($payload | ConvertTo-Json -Compress))
$unsigned = "$headerPart.$payloadPart"
$rsa = $cert.GetRSAPrivateKey()
if (-not $rsa) { throw 'RSA private key unavailable' }
try {
    $signature = $rsa.SignData(
        [Text.Encoding]::UTF8.GetBytes($unsigned),
        [Security.Cryptography.HashAlgorithmName]::SHA256,
        [Security.Cryptography.RSASignaturePadding]::Pkcs1
    )
} finally {
    $rsa.Dispose()
}
$assertion = "$unsigned.$(ConvertTo-Base64Url $signature)"

$body = @{
    client_id = $ClientId
    scope = 'https://graph.microsoft.com/.default'
    grant_type = 'client_credentials'
    client_assertion_type = 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer'
    client_assertion = $assertion
}

$response = Invoke-RestMethod -Method Post -Uri $aud -Body $body -ContentType 'application/x-www-form-urlencoded' -TimeoutSec 30
if (-not $response.access_token) { throw 'Microsoft identity platform returned no access_token' }

# This JSON is consumed directly by the local Python worker. Do not redirect it to logs.
[ordered]@{
    access_token = [string]$response.access_token
    expires_in = [int]$response.expires_in
    token_type = [string]$response.token_type
    certificate_thumbprint = $normalized
} | ConvertTo-Json -Compress
