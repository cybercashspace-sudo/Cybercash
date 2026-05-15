$ProgressPreference = 'SilentlyContinue'
function Get-GitHubHeaders {
  $inputText = "protocol=https`nhost=github.com`n`n"
  $credLines = $inputText | git credential-manager get
  $creds = @{}
  foreach ($line in $credLines) {
    if ($line -match '^(.*?)=(.*)$') { $creds[$matches[1]] = $matches[2] }
  }
  $pair = '{0}:{1}' -f $creds['username'], $creds['password']
  $basic = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes($pair))
  return @{ Authorization = "Basic $basic"; 'User-Agent' = 'codex-cli'; Accept = 'application/vnd.github+json' }
}
$headers = Get-GitHubHeaders
$outFile = Join-Path (Get-Location) 'job_73651285350_logs.txt'
Invoke-WebRequest -Headers $headers -Uri 'https://api.github.com/repos/cybercashspace-sudo/Cybercash/actions/jobs/73651285350/logs' -OutFile $outFile -MaximumRedirection 5 -TimeoutSec 120
Get-Item $outFile | Select-Object FullName,Length,LastWriteTime | ConvertTo-Json
