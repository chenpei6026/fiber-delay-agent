param([string]$Python = 'python')
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeRoot = Join-Path (Split-Path -Parent $projectRoot) '.runtime'
$server = Join-Path $runtimeRoot 'llama\llama-server.exe'
$model = Join-Path $runtimeRoot 'Qwen3-0.6B-Q8_0.gguf'
if (!(Test-Path -LiteralPath $server) -or !(Test-Path -LiteralPath $model)) { throw '请按 README 从官方来源下载模型与 llama.cpp。' }
Start-Process -FilePath $server -ArgumentList @('-m', ('"' + $model + '"'), '--host','127.0.0.1','--port','8081','-c','4096','-t','4','--jinja','--alias','Qwen3-0.6B-Q8_0') -WindowStyle Hidden
Set-Location -LiteralPath $projectRoot
& $Python -m src.web
