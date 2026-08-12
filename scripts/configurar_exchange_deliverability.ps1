$ErrorActionPreference = 'Stop'

$Sender = 'naoresponda@dev.shopvivaliz.com.br'
$SenderPattern = '^naoresponda@dev\.shopvivaliz\.com\.br$'

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
}

# Microsoft Graph MIME currently preserves List-Unsubscribe but the delivered
# Gmail sample did not contain List-Unsubscribe-Post. Add it in the Exchange
# transport pipeline so the final outbound message supports RFC 8058 one-click.
Ensure-HeaderRule `
    -Name 'ShopVivaliz MEI OneClick Unsubscribe' `
    -HeaderName 'List-Unsubscribe-Post' `
    -HeaderValue 'List-Unsubscribe=One-Click'

# Gmail Feedback Loop identifier. SenderId (VivalizMEI) is stable and 10 chars.
Ensure-HeaderRule `
    -Name 'ShopVivaliz MEI Gmail Feedback ID' `
    -HeaderName 'Feedback-ID' `
    -HeaderValue 'meimg:marketing:contamelo:VivalizMEI'

Write-Host "DELIVERABILITY_TRANSPORT_RULES_READY sender=$Sender"
Write-Host 'NOTE=Run in an authenticated Exchange Online PowerShell session with permission to manage transport rules.'
