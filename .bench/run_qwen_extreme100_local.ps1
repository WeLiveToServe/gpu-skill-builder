$ErrorActionPreference='Stop'
function Load-EnvFile([string]$path){
  if(!(Test-Path $path)){ return }
  Get-Content $path | ForEach-Object {
    $line=$_.Trim()
    if(!$line -or $line.StartsWith('#') -or -not $line.Contains('=')){ return }
    $kv=$line -split '=',2
    [Environment]::SetEnvironmentVariable($kv[0].Trim(),$kv[1],'Process')
  }
}
Load-EnvFile 'C:\Users\keith\dev\.env'
Load-EnvFile 'C:\Users\keith\dev\cli-harness\.env'
Load-EnvFile 'C:\Users\keith\dev\gpu-skill-builder\.env'
if(-not $env:OPENROUTER_API_KEY -and $env:HARNESS_OPENROUTER_API_KEY){ $env:OPENROUTER_API_KEY=$env:HARNESS_OPENROUTER_API_KEY }
if(-not $env:BENCH_OPENAI_BASE_URL){
  if($env:HARNESS_OPENROUTER_BASE_URL){ $env:BENCH_OPENAI_BASE_URL=$env:HARNESS_OPENROUTER_BASE_URL }
  elseif($env:OPENROUTER_BASE_URL){ $env:BENCH_OPENAI_BASE_URL=$env:OPENROUTER_BASE_URL }
  else { $env:BENCH_OPENAI_BASE_URL='https://openrouter.ai/api/v1' }
}
if(-not $env:BENCH_ANTHROPIC_BASE_URL){
  if($env:BENCH_OPENAI_BASE_URL.EndsWith('/v1')){ $env:BENCH_ANTHROPIC_BASE_URL=$env:BENCH_OPENAI_BASE_URL.Substring(0,$env:BENCH_OPENAI_BASE_URL.Length-3) }
  else { $env:BENCH_ANTHROPIC_BASE_URL=$env:BENCH_OPENAI_BASE_URL }
}
$model = if($env:BENCH_QWEN_MODEL){$env:BENCH_QWEN_MODEL}elseif($env:HARNESS_OPENROUTER_MODEL){$env:HARNESS_OPENROUTER_MODEL}elseif($env:OPENROUTER_MODEL){$env:OPENROUTER_MODEL}else{'qwen/qwen3.6-plus'}
$env:BENCH_QWEN_MODEL=$model
$env:BENCH_QWEN_CLI='C:\Users\keith\dev\cli-harness\qwen.cmd'
if(-not $env:OPENROUTER_API_KEY){ throw 'OPENROUTER_API_KEY missing' }
Set-Location 'C:\Users\keith\dev\gpu-skill-builder\.bench'
$log = Join-Path (Join-Path $PWD 'logs') ("qwen_extreme100_" + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.log')
"START $(Get-Date -Format o)" | Tee-Object -FilePath $log -Append
"BASE=$($env:BENCH_OPENAI_BASE_URL)" | Tee-Object -FilePath $log -Append
"MODEL=$model" | Tee-Object -FilePath $log -Append
python .\run_named_suite.py --harness qwen --suites extreme100 --timeout-s 1200 --ledger .\suite_runs_qwen_extreme100_gpu.json 2>&1 | Tee-Object -FilePath $log -Append
"END $(Get-Date -Format o) EXIT=$LASTEXITCODE" | Tee-Object -FilePath $log -Append
exit $LASTEXITCODE
