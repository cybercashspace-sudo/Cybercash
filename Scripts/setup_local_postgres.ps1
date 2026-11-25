$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$EnvPath = Join-Path $Root ".env"
$ServiceName = "postgresql-x64-18"
$DataDir = "C:\Program Files\PostgreSQL\18\data"
$BinDir = "C:\Program Files\PostgreSQL\18\bin"
$HbaPath = Join-Path $DataDir "pg_hba.conf"
$Psql = Join-Path $BinDir "psql.exe"
$SqlPath = Join-Path $env:TEMP "cybercash-local-postgres-setup.sql"

$Identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$Principal = [Security.Principal.WindowsPrincipal]::new($Identity)
if (-not $Principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run this script from an Administrator VS Code terminal. No database changes were made."
}
if (-not (Test-Path -LiteralPath $EnvPath)) { throw "Project .env was not found." }
if (-not (Test-Path -LiteralPath $HbaPath)) { throw "PostgreSQL data directory was not found at the configured local installation." }
if (-not (Test-Path -LiteralPath $Psql)) { throw "PostgreSQL psql.exe was not found." }

function Get-EnvValue([string]$Key) {
    $Matches = @(Get-Content -LiteralPath $EnvPath | Where-Object { $_ -match "^\s*$([regex]::Escape($Key))\s*=" })
    if ($Matches.Count -ne 1) { throw "Expected exactly one $Key setting in the root .env file." }
    return ($Matches[0] -split "=", 2)[1].Trim().Trim('"').Trim("'")
}

$SyncUrl = [Uri](Get-EnvValue "SYNC_DATABASE_URL")
$AsyncUrl = [Uri](Get-EnvValue "DATABASE_URL")
if ($SyncUrl.Host -ne "127.0.0.1" -or $SyncUrl.Port -ne 5433 -or $SyncUrl.AbsolutePath.TrimStart('/') -ne "cybercash") {
    throw "The configured sync URL must target the local cybercash database on port 5433."
}
if ($AsyncUrl.Host -ne $SyncUrl.Host -or $AsyncUrl.Port -ne $SyncUrl.Port -or $AsyncUrl.AbsolutePath -ne $SyncUrl.AbsolutePath) {
    throw "DATABASE_URL and SYNC_DATABASE_URL must target the same database."
}
$UserInfo = [Uri]::UnescapeDataString($SyncUrl.UserInfo) -split ":", 2
if ($UserInfo.Count -ne 2 -or $UserInfo[0] -ne "cyber_app" -or -not $UserInfo[1]) {
    throw "The .env sync URL must contain the cyber_app user and a password."
}
$AppPassword = $UserInfo[1]

$OriginalHba = [IO.File]::ReadAllBytes($HbaPath)
$TemporaryRule = [Text.Encoding]::ASCII.GetBytes("host all postgres 127.0.0.1/32 trust`r`n")
$TemporaryHba = New-Object byte[] ($TemporaryRule.Length + $OriginalHba.Length)
[Array]::Copy($TemporaryRule, 0, $TemporaryHba, 0, $TemporaryRule.Length)
[Array]::Copy($OriginalHba, 0, $TemporaryHba, $TemporaryRule.Length, $OriginalHba.Length)
$PreviousPgPassword = $env:PGPASSWORD
$AuthWasChanged = $false

function Restart-LocalPostgres {
    Restart-Service -Name $ServiceName -Force -ErrorAction Stop
    $Service = Get-Service -Name $ServiceName
    $Service.WaitForStatus([System.ServiceProcess.ServiceControllerStatus]::Running, [TimeSpan]::FromSeconds(45))
    Start-Sleep -Seconds 2
}

function Invoke-Psql([string[]]$Arguments) {
    & $Psql -P pager=off @Arguments
    if ($LASTEXITCODE -ne 0) { throw "psql failed with exit code $LASTEXITCODE." }
}

try {
    $Sql = @(
        '\set ON_ERROR_STOP on',
        '\getenv app_password PGPASSWORD',
        "SELECT format('CREATE ROLE cyber_app WITH LOGIN PASSWORD %L', :'app_password') WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'cyber_app')",
        '\gexec',
        "ALTER ROLE cyber_app WITH LOGIN PASSWORD :'app_password';",
        "SELECT 'CREATE DATABASE cybercash OWNER cyber_app' WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'cybercash')",
        '\gexec',
        'ALTER DATABASE cybercash OWNER TO cyber_app;',
        'GRANT ALL PRIVILEGES ON DATABASE cybercash TO cyber_app;'
    ) -join "`n"
    [IO.File]::WriteAllText($SqlPath, $Sql, [Text.UTF8Encoding]::new($false))

    [IO.File]::WriteAllBytes($HbaPath, $TemporaryHba)
    $AuthWasChanged = $true
    Restart-LocalPostgres

    $env:PGPASSWORD = $AppPassword
    Invoke-Psql @("--no-password", "-h", "127.0.0.1", "-p", "5433", "-U", "postgres", "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-f", $SqlPath)
    Invoke-Psql @("--no-password", "-h", "127.0.0.1", "-p", "5433", "-U", "postgres", "-d", "cybercash", "-v", "ON_ERROR_STOP=1", "-c", "ALTER SCHEMA public OWNER TO cyber_app; GRANT ALL PRIVILEGES ON SCHEMA public TO cyber_app; GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO cyber_app; GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO cyber_app; ALTER DEFAULT PRIVILEGES FOR ROLE cyber_app IN SCHEMA public GRANT ALL ON TABLES TO cyber_app; ALTER DEFAULT PRIVILEGES FOR ROLE cyber_app IN SCHEMA public GRANT ALL ON SEQUENCES TO cyber_app; SELECT count(*) AS existing_public_tables FROM information_schema.tables WHERE table_schema='public';")

    [IO.File]::WriteAllBytes($HbaPath, $OriginalHba)
    Restart-LocalPostgres
    $AuthWasChanged = $false

    Invoke-Psql @("--no-password", "-h", "127.0.0.1", "-p", "5433", "-U", "cyber_app", "-d", "cybercash", "-v", "ON_ERROR_STOP=1", "-c", "SELECT current_user, current_database(), inet_server_port();")
    Write-Host "PostgreSQL is configured and the app login was verified. Existing rows were preserved."
}
finally {
    if ($AuthWasChanged) {
        [IO.File]::WriteAllBytes($HbaPath, $OriginalHba)
        try {
            Restart-LocalPostgres
            $AuthWasChanged = $false
        } catch {
            Write-Error "Original PostgreSQL authentication file was restored, but service restart failed. Start the PostgreSQL service and rerun this script."
        }
    }
    if ($null -eq $PreviousPgPassword) { Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue }
    else { $env:PGPASSWORD = $PreviousPgPassword }
    Remove-Item -LiteralPath $SqlPath -Force -ErrorAction SilentlyContinue
}
