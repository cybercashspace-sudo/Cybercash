param(
    [int]$DatabaseReadyTimeoutSeconds = 800,
    [int]$BackendReadyTimeoutSeconds = 800,
    [int]$KivyReadyTimeoutSeconds = 800,
    [string]$BackendHost = "127.0.0.1",
    [int]$BackendPort = 8000,
    [string]$DatabaseHost = "127.0.0.1",
    [int]$DatabasePort = 5433,
    [string]$DatabaseName = "cybercash",
    [string]$DatabaseUser = "cyber_app"
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$PgBin = "C:\Program Files\PostgreSQL\18\bin"
$PgData = Join-Path $Root "postgres_local\runtime_data"
$LogDir = $Root
$BackendUrl = "http://${BackendHost}:${BackendPort}"
$BackendHealthUrl = "$BackendUrl/health"

function Write-Step {
    param([string]$Message)
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] $Message"
}

function Wait-Until {
    param(
        [scriptblock]$Condition,
        [int]$TimeoutSeconds,
        [string]$WaitingMessage,
        [string]$TimeoutMessage
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (& $Condition) {
            return
        }
        Start-Sleep -Seconds 2
        Write-Step $WaitingMessage
    }

    throw $TimeoutMessage
}

function Test-CommandSuccess {
    param([scriptblock]$Command)
    try {
        & $Command | Out-Null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Resolve-Python {
    $candidates = @(
        (Join-Path $Root ".venv\Scripts\python.exe"),
        (Join-Path $Root "venv\Scripts\python.exe"),
        (Join-Path $Root "backend\venv\Scripts\python.exe"),
        "C:\Users\CYBER360\AppData\Local\Programs\Python\Python311\python.exe",
        "C:\Python314\python.exe",
        "python.exe"
    )

    foreach ($candidate in $candidates) {
        $resolved = Get-Command $candidate -ErrorAction SilentlyContinue
        if (-not $resolved) {
            continue
        }

        $path = $resolved.Source
        try {
            $probe = & $path -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $probe) {
                return $path
            }
        } catch {
            continue
        }
    }

    throw @"
No working Python interpreter was found.

Expected one of these to work:
- .\.venv\Scripts\python.exe
- .\venv\Scripts\python.exe
- .\backend\venv\Scripts\python.exe
- C:\Users\CYBER360\AppData\Local\Programs\Python\Python311\python.exe
- C:\Python314\python.exe

Restore Python first, then rerun:
powershell -ExecutionPolicy Bypass -File .\start_stack_800.ps1
"@
}

function Start-Postgres {
    $postgres = Join-Path $PgBin "postgres.exe"
    $initdb = Join-Path $PgBin "initdb.exe"
    $pgIsReady = Join-Path $PgBin "pg_isready.exe"
    $createdb = Join-Path $PgBin "createdb.exe"
    $psql = Join-Path $PgBin "psql.exe"

    if (-not (Test-Path $postgres)) {
        throw "PostgreSQL was not found at $postgres"
    }

    if (-not (Test-Path (Join-Path $PgData "PG_VERSION"))) {
        Write-Step "Initializing PostgreSQL data directory at $PgData"
        New-Item -ItemType Directory -Force -Path $PgData | Out-Null
        & $initdb -D $PgData -U $DatabaseUser -A trust --encoding=UTF8 --locale=C
    }

    $ready = Test-CommandSuccess { & $pgIsReady -h $DatabaseHost -p $DatabasePort -U $DatabaseUser -d postgres }
    if (-not $ready) {
        $pidFile = Join-Path $PgData "postmaster.pid"
        if (Test-Path $pidFile) {
            $pidLine = Get-Content $pidFile -TotalCount 1 -ErrorAction SilentlyContinue
            $pidProcess = $null
            if ($pidLine -match "^\d+$") {
                $pidProcess = Get-Process -Id ([int]$pidLine) -ErrorAction SilentlyContinue
            }
            if (-not $pidProcess) {
                Write-Step "Removing stale PostgreSQL PID file"
                Remove-Item -LiteralPath $pidFile -Force
            }
        }

        Write-Step "Starting PostgreSQL on ${DatabaseHost}:${DatabasePort}"
        Start-Process `
            -FilePath $postgres `
            -ArgumentList @("-D", $PgData, "-p", "$DatabasePort", "-h", $DatabaseHost) `
            -WorkingDirectory $Root `
            -RedirectStandardOutput (Join-Path $LogDir "postgres_runtime.out.log") `
            -RedirectStandardError (Join-Path $LogDir "postgres_runtime.err.log") `
            -WindowStyle Hidden | Out-Null
    }

    Wait-Until `
        -TimeoutSeconds $DatabaseReadyTimeoutSeconds `
        -WaitingMessage "Waiting for PostgreSQL for up to $DatabaseReadyTimeoutSeconds seconds..." `
        -TimeoutMessage "PostgreSQL did not become ready within $DatabaseReadyTimeoutSeconds seconds." `
        -Condition { Test-CommandSuccess { & $pgIsReady -h $DatabaseHost -p $DatabasePort -U $DatabaseUser -d postgres } }

    Write-Step "PostgreSQL ready on ${DatabaseHost}:${DatabasePort}"

    $existsRows = @(& $psql -h $DatabaseHost -p $DatabasePort -U $DatabaseUser -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$DatabaseName';" 2>$null)
    if ($LASTEXITCODE -ne 0) {
        throw "Could not query PostgreSQL with psql."
    }
    $exists = $existsRows | Where-Object { $_ -and $_.Trim() } | Select-Object -First 1
    if (-not $exists -or $exists.Trim() -ne "1") {
        Write-Step "Creating database $DatabaseName"
        & $createdb -h $DatabaseHost -p $DatabasePort -U $DatabaseUser $DatabaseName
        if ($LASTEXITCODE -ne 0) {
            throw "Could not create database $DatabaseName."
        }
    }
}

function Start-Backend {
    param([string]$Python)

    $env:DATABASE_URL = "postgresql+asyncpg://${DatabaseUser}@${DatabaseHost}:${DatabasePort}/${DatabaseName}"
    $env:SYNC_DATABASE_URL = "postgresql+psycopg2://${DatabaseUser}@${DatabaseHost}:${DatabasePort}/${DatabaseName}"
    $env:KIVY_API_URL = $BackendUrl
    $env:CYBERCASH_API_URL = $BackendUrl
    $env:BACKEND_URL = $BackendUrl
    $env:PYTHONPATH = $Root

    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $BackendHealthUrl -TimeoutSec 3
        if ($response.StatusCode -eq 200) {
            Write-Step "Backend already healthy at $BackendHealthUrl"
            return
        }
    } catch {
        Write-Step "Starting backend on $BackendHealthUrl"
    }

    Start-Process `
        -FilePath $Python `
        -ArgumentList @("-m", "uvicorn", "backend.main:app", "--host", $BackendHost, "--port", "$BackendPort") `
        -WorkingDirectory $Root `
        -RedirectStandardOutput (Join-Path $LogDir "backend_runtime.out.log") `
        -RedirectStandardError (Join-Path $LogDir "backend_runtime.err.log") `
        -WindowStyle Hidden | Out-Null

    Wait-Until `
        -TimeoutSeconds $BackendReadyTimeoutSeconds `
        -WaitingMessage "Waiting for backend health for up to $BackendReadyTimeoutSeconds seconds..." `
        -TimeoutMessage "Backend health check did not pass within $BackendReadyTimeoutSeconds seconds." `
        -Condition {
            try {
                $response = Invoke-WebRequest -UseBasicParsing -Uri $BackendHealthUrl -TimeoutSec 3
                return $response.StatusCode -eq 200
            } catch {
                return $false
            }
        }

    Write-Step "Backend health check: 200"
}

function Start-Kivy {
    param([string]$Python)

    $env:KIVY_HOME = Join-Path $Root ".kivy_runtime"
    $env:KIVY_API_URL = $BackendUrl
    $env:CYBERCASH_API_URL = $BackendUrl
    $env:BACKEND_URL = $BackendUrl
    $env:PYTHONPATH = $Root

    Write-Step "Starting Kivy with KIVY_API_URL=$BackendUrl"
    $process = Start-Process `
        -FilePath $Python `
        -ArgumentList @("main.py") `
        -WorkingDirectory $Root `
        -RedirectStandardOutput (Join-Path $LogDir "kivy_runtime.out.log") `
        -RedirectStandardError (Join-Path $LogDir "kivy_runtime.err.log") `
        -PassThru

    Wait-Until `
        -TimeoutSeconds $KivyReadyTimeoutSeconds `
        -WaitingMessage "Waiting for Kivy to stay alive for up to $KivyReadyTimeoutSeconds seconds..." `
        -TimeoutMessage "Kivy exited before it could stay running." `
        -Condition {
            Start-Sleep -Seconds 3
            return -not $process.HasExited
        }

    Write-Step "Kivy started, process id $($process.Id)"
}

Write-Step "Using 800-second readiness windows: database=$DatabaseReadyTimeoutSeconds, backend=$BackendReadyTimeoutSeconds, kivy=$KivyReadyTimeoutSeconds"
Start-Postgres
$Python = Resolve-Python
Write-Step "Using Python: $Python"
Start-Backend -Python $Python
Start-Kivy -Python $Python
Write-Step "Stack started successfully."
