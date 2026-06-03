<#
.SYNOPSIS
Sync selected local .env values to an existing Render service without printing secrets.

.EXAMPLE
$env:RENDER_API_KEY = "rnd_..."
$env:RENDER_SERVICE_ID = "srv_..."
powershell -ExecutionPolicy Bypass -File .\deployment\sync_render_env.ps1 -Deploy

.NOTES
By default this syncs API credentials and integration settings only. It skips
empty values and local runtime keys such as DATABASE_URL, ENV, and PORT.
#>

[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$EnvFile = ".env",
    [string]$ServiceId = $env:RENDER_SERVICE_ID,
    [string]$ApiKey = $env:RENDER_API_KEY,
    [string[]]$IncludeKeys = @(),
    [string[]]$ExcludeKeys = @(),
    [switch]$AllKeys,
    [switch]$IncludeEmpty,
    [switch]$Deploy
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$DefaultSyncKeys = @(
    "SECRET_KEY",
    "MAIL_USERNAME",
    "MAIL_PASSWORD",
    "MAIL_FROM",
    "MAIL_PORT",
    "MAIL_SERVER",
    "MAIL_FROM_NAME",
    "OTP_PROVIDER",
    "SMS_PROVIDER",
    "SMS_SENDER_ID",
    "MNOTIFY_API_KEY",
    "MNOTIFY_SENDER",
    "MNOTIFY_SMS_URL",
    "HUBTEL_AUTH",
    "HUBTEL_CLIENT_ID",
    "HUBTEL_CLIENT_SECRET",
    "HUBTEL_BASE_URL",
    "HUBTEL_SMS_URL",
    "HUBTEL_SENDER_ID",
    "HUBTEL_COUNTRY_CODE",
    "HUBTEL_TIMEOUT_SECONDS",
    "ARKESEL_API_KEY",
    "ARKESEL_SENDER_ID",
    "ARKESEL_SMS_URL",
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "TWILIO_MESSAGING_SERVICE_SID",
    "TWILIO_FROM_NUMBER",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "PAYSTACK_PUBLIC_KEY",
    "PAYSTACK_SECRET_KEY",
    "PAYSTACK_SECRET",
    "PAYSTACK_API_SECRET_KEY",
    "PAYSTACK_LIVE_SECRET_KEY",
    "PAYSTACK_TEST_SECRET_KEY",
    "PAYSTACK_BASE_URL",
    "PAYSTACK_WALLET_CALLBACK_URL",
    "PAYSTACK_MIN_WALLET_TOPUP_GHS",
    "PAYSTACK_MAX_WALLET_TOPUP_GHS",
    "PAYSTACK_FALLBACK_EMAIL_DOMAIN",
    "FLUTTERWAVE_BASE_URL",
    "FLUTTERWAVE_TOKEN_URL",
    "FLW_CLIENT_ID",
    "FLW_CLIENT_SECRET",
    "FLW_ENCRYPTION_KEY",
    "FLUTTERWAVE_SECRET_KEY",
    "FLUTTERWAVE_WEBHOOK_HASH",
    "BINANCE_API_KEY",
    "BINANCE_SECRET_KEY",
    "BINANCE_API_SECRET",
    "BINANCE_BASE_URL",
    "BINANCE_TIMEOUT_SECONDS",
    "BINANCE_RECV_WINDOW",
    "BINANCE_WITHDRAWALS_ENABLED",
    "IDATA_API_KEY",
    "IDATA_BASE_URL",
    "IDATA_TIMEOUT_SECONDS",
    "IDATA_USER_MARKUP_PERCENTAGE",
    "IDATA_USER_MARKUP_GHS",
    "IDATA_SEND_SMS",
    "AIRTIME_CASH_SMS_WEBHOOK_TOKEN",
    "AIRTIME_CASH_MOMO_CALLBACK_URL",
    "CARD_PROCESSOR_WEBHOOK_KEY"
)

$AlwaysExcludeKeys = @(
    "RENDER_API_KEY",
    "RENDER_SERVICE_ID",
    "RENDER_ENV_FILE",
    "ENV",
    "PORT",
    "RUNNING_TESTS",
    "DATABASE_URL",
    "SYNC_DATABASE_URL",
    "KIVY_API_URL",
    "CYBERCASH_API_URL",
    "BACKEND_URL"
)

function ConvertFrom-DotEnv {
    param([string]$Path)

    $values = [ordered]@{}
    foreach ($line in Get-Content -LiteralPath $Path) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }

        if ($line.TrimStart().StartsWith("#")) {
            continue
        }

        if ($line -notmatch '^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$') {
            continue
        }

        $key = $matches[1]
        $value = $matches[2].Trim()

        if ($value.Length -ge 2) {
            $first = $value.Substring(0, 1)
            $last = $value.Substring($value.Length - 1, 1)
            if (($first -eq '"' -and $last -eq '"') -or ($first -eq "'" -and $last -eq "'")) {
                $value = $value.Substring(1, $value.Length - 2)
            }
        }

        if ($values.Contains($key)) {
            $values[$key] = $value
        }
        else {
            $values.Add($key, $value)
        }
    }

    return $values
}

if (-not (Test-Path -LiteralPath $EnvFile)) {
    throw "Env file not found: $EnvFile"
}

$localEnv = ConvertFrom-DotEnv -Path $EnvFile

if ([string]::IsNullOrWhiteSpace($ApiKey) -and $localEnv.Contains("RENDER_API_KEY")) {
    $ApiKey = [string]$localEnv["RENDER_API_KEY"]
}

if ([string]::IsNullOrWhiteSpace($ServiceId) -and $localEnv.Contains("RENDER_SERVICE_ID")) {
    $ServiceId = [string]$localEnv["RENDER_SERVICE_ID"]
}

if ([string]::IsNullOrWhiteSpace($ApiKey)) {
    throw "Missing Render API key. Set RENDER_API_KEY locally or pass -ApiKey. Do not commit it."
}

if ([string]::IsNullOrWhiteSpace($ServiceId)) {
    throw "Missing Render service ID. Set RENDER_SERVICE_ID locally or pass -ServiceId."
}

$candidateKeys = if ($AllKeys) {
    @($localEnv.Keys)
}
else {
    @($DefaultSyncKeys + $IncludeKeys)
}

$excluded = @{}
foreach ($key in @($AlwaysExcludeKeys + $ExcludeKeys)) {
    $excluded[$key] = $true
}

$keysToSync = @()
foreach ($key in ($candidateKeys | Sort-Object -Unique)) {
    if (-not $localEnv.Contains($key)) {
        continue
    }

    if ($excluded.Contains($key)) {
        continue
    }

    $value = [string]$localEnv[$key]
    if (-not $IncludeEmpty -and [string]::IsNullOrWhiteSpace($value)) {
        continue
    }

    $keysToSync += $key
}

if ($keysToSync.Count -eq 0) {
    Write-Host "No non-empty Render environment variables selected for sync."
    exit 0
}

$headers = @{
    "Accept" = "application/json"
    "Content-Type" = "application/json"
    "Authorization" = "Bearer $ApiKey"
}

$baseUrl = "https://api.render.com/v1"
$synced = @()

foreach ($key in $keysToSync) {
    $encodedKey = [System.Uri]::EscapeDataString($key)
    $uri = "$baseUrl/services/$ServiceId/env-vars/$encodedKey"
    $body = @{ value = [string]$localEnv[$key] } | ConvertTo-Json -Compress

    if ($PSCmdlet.ShouldProcess("Render service $ServiceId", "set $key")) {
        Invoke-RestMethod -Method Put -Uri $uri -Headers $headers -Body $body | Out-Null
    }

    $synced += $key
}

Write-Host ("Synced {0} Render environment variables: {1}" -f $synced.Count, ($synced -join ", "))

if ($Deploy) {
    $deployUri = "$baseUrl/services/$ServiceId/deploys"
    $deployBody = @{ clearCache = "do_not_clear" } | ConvertTo-Json -Compress

    if ($PSCmdlet.ShouldProcess("Render service $ServiceId", "trigger deploy")) {
        Invoke-RestMethod -Method Post -Uri $deployUri -Headers $headers -Body $deployBody | Out-Null
    }

    Write-Host "Triggered a Render deploy for the updated service."
}
