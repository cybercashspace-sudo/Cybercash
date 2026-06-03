param(
    [decimal]$Amount = 1,
    [string]$Serial = "R83YC078RGM",
    [string]$BaseUrl = "https://cybercash.space"
)

$ErrorActionPreference = "Stop"

$sessionJson = adb -s $Serial shell run-as org.cybercash.cybercash cat files/session.json
$session = $sessionJson | ConvertFrom-Json
$token = $session.auth.access_token
if ([string]::IsNullOrWhiteSpace($token)) {
    throw "No phone session token found."
}

$headers = @{
    Authorization = "Bearer $token"
    "Content-Type" = "application/json"
}
$body = @{ amount = [double]$Amount } | ConvertTo-Json
$uri = "$($BaseUrl.TrimEnd('/'))/paystack/initiate"

try {
    $response = Invoke-WebRequest -Uri $uri -Method Post -Headers $headers -Body $body -TimeoutSec 60
    [pscustomobject]@{
        status = [int]$response.StatusCode
        body = $response.Content
    } | ConvertTo-Json -Depth 6
} catch {
    $webResponse = $_.Exception.Response
    if ($webResponse) {
        $reader = [System.IO.StreamReader]::new($webResponse.GetResponseStream())
        try {
            $responseBody = $reader.ReadToEnd()
        } finally {
            $reader.Dispose()
        }
        [pscustomobject]@{
            status = [int]$webResponse.StatusCode
            body = $responseBody
        } | ConvertTo-Json -Depth 6
    } else {
        [pscustomobject]@{
            status = 0
            body = $_.Exception.Message
        } | ConvertTo-Json -Depth 6
    }
}
