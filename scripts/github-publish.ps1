param([switch]$Publish)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
# Keep credentials in memory. Never print or persist the password/token.
$credentialText = ("protocol=https`nhost=github.com`nusername=chenpei6026`n`n" | git credential fill) -join "`n"
$credential = @{}
foreach ($line in ($credentialText -split "`n")) {
    $parts = $line -split '=',2
    if ($parts.Count -eq 2) { $credential[$parts[0]] = $parts[1] }
}
if (!$credential['password']) { throw 'GitHub login required.' }
$headers = @{Authorization=('Bearer '+$credential['password']); Accept='application/vnd.github+json'; 'User-Agent'='FiberScope-course-project'}
$account = Invoke-RestMethod -Uri 'https://api.github.com/user' -Headers $headers
if ($account.login -ne 'chenpei6026') { throw 'Unexpected GitHub account.' }
if (!$Publish) { Write-Output ('Authenticated account: '+$account.login); exit }
$repoName = 'fiber-delay-agent'
$repoUrl = 'https://api.github.com/repos/chenpei6026/'+$repoName
$repository = $null
try { $repository = Invoke-RestMethod -Uri $repoUrl -Headers $headers }
catch { if ([int]$_.Exception.Response.StatusCode -ne 404) { throw } }
if (!$repository) {
    $body = @{name=$repoName;description='FiberScope: optical link delay diagnosis with a small local LLM and verifiable network tools';private=$false;auto_init=$false} | ConvertTo-Json
    $repository = Invoke-RestMethod -Method Post -Uri 'https://api.github.com/user/repos' -Headers $headers -ContentType 'application/json' -Body $body
}
if (!(Test-Path -LiteralPath '.git')) { git init -b main }
git config user.name 'chenpei6026'
git config user.email 'chenpei6026@users.noreply.github.com'
git add .
git commit -m 'Complete FiberScope coursework implementation, report and reproducible evaluation'
$remotes = @(git remote)
if ($remotes -contains 'origin') {
    $origin = git remote get-url origin
    if ($origin -ne $repository.clone_url) { throw 'Existing origin differs; stopping.' }
} else { git remote add origin $repository.clone_url }
git push -u origin main
if ($LASTEXITCODE -ne 0) { throw 'Git push failed.' }
$verified = Invoke-RestMethod -Uri ($repoUrl+'/commits/main') -Headers $headers
Write-Output ('Published: '+$repository.html_url)
Write-Output ('Verified commit: '+$verified.sha)
