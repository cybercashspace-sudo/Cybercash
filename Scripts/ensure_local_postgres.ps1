param(
    [string]$HostName = "127.0.0.1",
    [int]$Port = 5433,
    [string]$Database = "cybercash",
    [string]$User = "postgres",
    [string]$Password = "postgres"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $repoRoot ".env"
$asyncUrl = "postgresql+asyncpg://$User`:$Password@$HostName`:$Port/$Database"
$syncUrl = "postgresql://$User`:$Password@$HostName`:$Port/$Database"

function Find-PostgresTool {
    param([string]$ToolName)

    $fromPath = Get-Command $ToolName -ErrorAction SilentlyContinue
    if ($fromPath) {
        return $fromPath.Source
    }

    $pgRoot = "C:\Program Files\PostgreSQL"
    if (Test-Path $pgRoot) {
        $versions = Get-ChildItem -Path $pgRoot -Directory -ErrorAction SilentlyContinue |
            Sort-Object Name -Descending
        foreach ($version in $versions) {
            $candidate = Join-Path $version.FullName "bin\$ToolName.exe"
            if (Test-Path $candidate) {
                return $candidate
            }
        }
    }

    return $null
}

function Update-DotEnvDatabaseUrls {
    $lines = @()
    if (Test-Path $envPath) {
        $lines = Get-Content -Path $envPath
    }

    $filtered = New-Object System.Collections.Generic.List[string]
    foreach ($line in $lines) {
        if ($line -match '^\s*#?\s*(DATABASE_URL|SYNC_DATABASE_URL)\s*=') {
            continue
        }
        $filtered.Add($line)
    }

    while ($filtered.Count -gt 0 -and [string]::IsNullOrWhiteSpace($filtered[$filtered.Count - 1])) {
        $filtered.RemoveAt($filtered.Count - 1)
    }

    if ($filtered.Count -gt 0) {
        $filtered.Add("")
    }

    $filtered.Add("DATABASE_URL=$asyncUrl")
    $filtered.Add("SYNC_DATABASE_URL=$syncUrl")

    Set-Content -Path $envPath -Value $filtered -Encoding UTF8
}

function Ensure-LocalPostgresCluster {
    $initdb = Find-PostgresTool "initdb"
    $pgCtl = Find-PostgresTool "pg_ctl"
    $pgReady = Find-PostgresTool "pg_isready"
    if (-not $initdb -or -not $pgCtl -or -not $pgReady) {
        throw "PostgreSQL tools were not found. Install PostgreSQL or add its bin directory to PATH."
    }

    $dataDir = Join-Path $repoRoot ".local_pgdata"
    $logDir = Join-Path $repoRoot ".local_pglog"
    $logFile = Join-Path $logDir "postgres.log"
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null

    if (-not (Test-Path (Join-Path $dataDir "PG_VERSION"))) {
        $pwFile = Join-Path ([System.IO.Path]::GetTempPath()) ("cybercash-pg-" + [System.Guid]::NewGuid().ToString("N") + ".txt")
        Set-Content -Path $pwFile -Value $Password -Encoding ASCII
        try {
            & $initdb -D $dataDir -U $User -A scram-sha-256 --pwfile $pwFile | Out-Null
            if ($LASTEXITCODE -ne 0) {
                throw "Failed to initialize local PostgreSQL data directory at $dataDir."
            }
        }
        finally {
            Remove-Item -LiteralPath $pwFile -Force -ErrorAction SilentlyContinue
        }
    }

    & $pgCtl -D $dataDir -l $logFile -o "-p $Port -h $HostName" start | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to start local PostgreSQL cluster on $HostName`:$Port. See $logFile."
    }

    $deadline = (Get-Date).AddSeconds(20)
    do {
        & $pgReady -h $HostName -p $Port -U $User | Out-Null
        if ($LASTEXITCODE -eq 0) {
            return
        }
        Start-Sleep -Seconds 1
    } while ((Get-Date) -lt $deadline)

    throw "Local PostgreSQL cluster started, but did not become ready on $HostName`:$Port. See $logFile."
}

function Ensure-Database {
    $psql = Find-PostgresTool "psql"
    if (-not $psql) {
        throw "psql was not found. Install PostgreSQL or add its bin directory to PATH."
    }

    $previousPassword = $env:PGPASSWORD
    $previousConnectTimeout = $env:PGCONNECT_TIMEOUT
    $env:PGPASSWORD = $Password
    $env:PGCONNECT_TIMEOUT = "5"
    try {
        $previousErrorAction = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        try {
            $exists = & $psql -h $HostName -p $Port -U $User -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$Database';" 2>$null
            $probeExitCode = $LASTEXITCODE
        }
        finally {
            $ErrorActionPreference = $previousErrorAction
        }

        if ($probeExitCode -ne 0) {
            Ensure-LocalPostgresCluster
            $exists = & $psql -h $HostName -p $Port -U $User -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$Database';"
        }

        if ($LASTEXITCODE -ne 0) {
            throw "Unable to connect to PostgreSQL at $HostName`:$Port as $User."
        }

        if (($exists | Select-Object -First 1).Trim() -ne "1") {
            & $psql -h $HostName -p $Port -U $User -d postgres -c "CREATE DATABASE `"$Database`";" | Out-Null
            if ($LASTEXITCODE -ne 0) {
                throw "Failed to create PostgreSQL database '$Database'."
            }
        }

        & $psql -h $HostName -p $Port -U $User -d $Database -tAc "SELECT 1;" | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Created or found '$Database', but verification query failed."
        }
    }
    finally {
        $env:PGPASSWORD = $previousPassword
        $env:PGCONNECT_TIMEOUT = $previousConnectTimeout
    }
}

Update-DotEnvDatabaseUrls
Ensure-Database

Write-Host "Local PostgreSQL env is set for $Database at $HostName`:$Port."
