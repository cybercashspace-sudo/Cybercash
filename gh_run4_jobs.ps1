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
$jobs = Invoke-RestMethod -Headers $headers -Uri 'https://api.github.com/repos/cybercashspace-sudo/Cybercash/actions/runs/25129413157/jobs' -Method Get -TimeoutSec 120
$jobs.jobs | Select-Object id,name,status,conclusion,started_at,completed_at,html_url | ConvertTo-Json -Depth 4
