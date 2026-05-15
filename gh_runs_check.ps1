$ProgressPreference = 'SilentlyContinue'
function Get-GitHubHeaders {
  $inputText = "protocol=https`nhost=github.com`n`n"
  $credLines = $inputText | git credential-manager get
  $creds = @{}
  foreach ($line in $credLines) {
    if ($line -match '^(.*?)=(.*)$') { $creds[$matches[1]] = $matches[2] }
  }
  if (-not $creds.ContainsKey('username') -or -not $creds.ContainsKey('password')) {
    throw 'GitHub credentials not available from git credential manager.'
  }
  $pair = '{0}:{1}' -f $creds['username'], $creds['password']
  $basic = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes($pair))
  return @{ Authorization = "Basic $basic"; 'User-Agent' = 'codex-cli'; Accept = 'application/vnd.github+json' }
}
$headers = Get-GitHubHeaders
$runs = Invoke-RestMethod -Headers $headers -Uri 'https://api.github.com/repos/cybercashspace-sudo/Cybercash/actions/runs?per_page=5' -Method Get -TimeoutSec 120
$runs.workflow_runs | Select-Object -First 5 id,name,status,conclusion,html_url,head_sha,created_at,updated_at | ConvertTo-Json -Depth 4
