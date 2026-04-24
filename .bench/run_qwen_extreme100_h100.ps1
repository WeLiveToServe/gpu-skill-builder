$ErrorActionPreference='Stop'
function Load-EnvFile([string]$path){
  if(!(Test-Path $path)){ return }
  Get-Content $path | ForEach-Object {
    $line=$_.Trim()
    if(!$line -or $line.StartsWith('#') -or -not $line.Contains('=')){ return }
    $kv=$line -split '=',2
    [Environment]::SetEnvironmentVariable($kv[0].Trim(),$kv[1].Trim(),'Process')
  }
}
Load-EnvFile 'C:\Users\keith\dev\.env'
Load-EnvFile 'C:\Users\keith\dev\cli-harness\.env'
Load-EnvFile 'C:\Users\keith\dev\gpu-skill-builder\.env'

$gpuBase='http://157.245.71.5:8000/v1'
$gpuModel='google/gemma-4-31B-it'
$env:HARNESS_OPENROUTER_BASE_URL=$gpuBase
$env:HARNESS_OPENROUTER_MODEL=$gpuModel
if($env:DO_H100_API_KEY){ $env:HARNESS_OPENROUTER_API_KEY=$env:DO_H100_API_KEY }
if(-not $env:HARNESS_OPENROUTER_API_KEY -and $env:OPENROUTER_API_KEY){ $env:HARNESS_OPENROUTER_API_KEY=$env:OPENROUTER_API_KEY }

$env:BENCH_OPENAI_BASE_URL=$gpuBase
$env:BENCH_QWEN_MODEL=$gpuModel
$env:BENCH_QWEN_CLI='C:\Users\keith\dev\cli-harness\qwen.cmd'

Set-Location 'C:\Users\keith\dev\gpu-skill-builder\.bench'
$logs = Join-Path $PWD 'logs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null
$log = Join-Path $logs ('qwen_extreme100_h100_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.log')
"START $(Get-Date -Format o)" | Tee-Object -FilePath $log -Append
"BASE=$gpuBase" | Tee-Object -FilePath $log -Append
"MODEL=$gpuModel" | Tee-Object -FilePath $log -Append
python .\run_named_suite.py --harness qwen --suites extreme100 --timeout-s 1200 --ledger .\suite_runs_qwen_extreme100_gpu.json 2>&1 | Tee-Object -FilePath $log -Append
"END $(Get-Date -Format o) EXIT=$LASTEXITCODE" | Tee-Object -FilePath $log -Append
exit $LASTEXITCODE
