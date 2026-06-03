$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Script = Join-Path $Root "ensure_postgres_database.py"

$ManagedPythonRoot = Join-Path $env:APPDATA "uv\python"
$ManagedPython = Get-ChildItem -Path $ManagedPythonRoot -Filter "python.exe" -Recurse -ErrorAction SilentlyContinue |
    Where-Object { -not $_.FullName.StartsWith($Root, [System.StringComparison]::OrdinalIgnoreCase) } |
    Sort-Object FullName -Descending |
    Select-Object -First 1

$Launchers = @(
    @{ Source = $(if ($ManagedPython) { $ManagedPython.FullName } else { $null }); Command = $null; ExtraArgs = @() },
    @{ Command = "py"; ExtraArgs = @("-3") },
    @{ Command = "python"; ExtraArgs = @() }
)

foreach ($Launcher in $Launchers) {
    try {
        $Source = $Launcher.Source
        if (-not $Source) {
            if (-not $Launcher.Command) {
                continue
            }
            $Resolved = Get-Command $Launcher.Command -ErrorAction Stop
            $Source = $Resolved.Source
        }
        if ($Source) {
            $ResolvedPath = [System.IO.Path]::GetFullPath($Source)
            if ($ResolvedPath.StartsWith($Root, [System.StringComparison]::OrdinalIgnoreCase)) {
                continue
            }
        }

        & $Source @($Launcher.ExtraArgs + @($Script))
        exit $LASTEXITCODE
    } catch {
        if ($Launcher -eq $Launchers[-1]) {
            throw
        }
    }
}
