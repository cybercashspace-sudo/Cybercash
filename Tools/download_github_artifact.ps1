param(
    [Parameter(Mandatory = $true)]
    [string]$ArtifactId,

    [Parameter(Mandatory = $true)]
    [string]$OutputPath,

    [switch]$ResumeWithCurl
)

$ErrorActionPreference = "Stop"

$outputDir = Split-Path -Parent $OutputPath
if ($outputDir) {
    New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
}
$resolvedOutputPath = [System.IO.Path]::GetFullPath($OutputPath)

$credentialQuery = "protocol=https`nhost=github.com`n`n"
$filledCredential = $credentialQuery | git credential fill
$tokenLine = $filledCredential -split "`n" | Where-Object { $_ -like "password=*" } | Select-Object -First 1

if ([string]::IsNullOrWhiteSpace($tokenLine)) {
    throw "No saved GitHub credential token is available."
}

$token = $tokenLine.Substring("password=".Length)
$headers = @{
    Authorization = "Bearer $token"
    "User-Agent" = "Codex"
}

$uri = "https://api.github.com/repos/cybercashspace-sudo/Cybercash/actions/artifacts/$ArtifactId/zip"

$downloaded = $false
if (-not $ResumeWithCurl) {
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        try {
            if (Test-Path $resolvedOutputPath) {
                Remove-Item -LiteralPath $resolvedOutputPath -Force
            }
            Invoke-WebRequest -Uri $uri -Headers $headers -OutFile $resolvedOutputPath
            $downloaded = $true
            break
        } catch {
            if ($attempt -eq 3) {
                Write-Warning "PowerShell download failed after $attempt attempts: $($_.Exception.Message)"
            } else {
                Start-Sleep -Seconds (5 * $attempt)
            }
        }
    }
}

if (-not $downloaded) {
    $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
    if (-not $curl) {
        throw "curl.exe is not available for fallback artifact download."
    }
    $curlOutputPath = $resolvedOutputPath -replace "\\", "/"
    & $curl.Source -L -C - --retry 10 --retry-delay 5 --connect-timeout 60 `
        -H "Authorization: Bearer $token" `
        -H "User-Agent: Codex" `
        -o $curlOutputPath `
        $uri
    if ($LASTEXITCODE -ne 0) {
        throw "curl.exe artifact download failed with exit code $LASTEXITCODE."
    }
}

Get-Item $resolvedOutputPath | Select-Object FullName, Length
