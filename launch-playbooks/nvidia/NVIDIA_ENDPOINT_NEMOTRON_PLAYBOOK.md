# NVIDIA NIM Endpoint Connectivity and Nemotron Validation Log

Date: 2026-04-17  
Operator: Codex agent  
Workspace: `C:\Users\keith\dev\gpu-skill-builder`

## Goal
Validate NVIDIA hosted endpoint connectivity, enumerate available models, and test Nemotron model invocation with exact OpenAI-compatible API calls.

## Exact User Prompt That Triggered This Run
`please search docs to find the url for the correct endpoint and ping it with the key`  
`try and connect to the nemotron 4 model. get the correct name from the docs or endpoint`  
`try again with the specific steps listed`

## Prereqs Used
- NVIDIA key in env: `NVIDIA_API_KEY=nvapi-...`
- Endpoint base URL: `https://integrate.api.nvidia.com/v1`
- PowerShell with `Invoke-RestMethod`

## Exact Commands Run (PowerShell)

### 1. Load key from `C:\Users\keith\dev\.env`
```powershell
$ErrorActionPreference='Stop'
$envFile='C:\Users\keith\dev\.env'
$keyLine = Get-Content $envFile | Where-Object { $_ -match '^NVIDIA_API_KEY=' } | Select-Object -First 1
$apiKey = ($keyLine -split '=',2)[1].Trim().Trim('"')
$base='https://integrate.api.nvidia.com/v1'
$headers=@{ Authorization = "Bearer $apiKey" }
```

### 2. Query available models
```powershell
$modelsResp = Invoke-RestMethod -Method GET -Uri "$base/models" -Headers $headers
$allModels = @($modelsResp.data.id)
"Model count: $($allModels.Count)"
$allModels | Select-Object -First 20
```

### 3. Check specific target model IDs
```powershell
$targets = @(
  'nvidia/nemotron-3-super-120b-a12b',
  'nvidia/nemotron-4-340b-instruct',
  'nvidia/llama-3.1-nemotron-70b-instruct',
  'meta/llama-3.1-8b-instruct'
)
foreach ($t in $targets) {
  if ($allModels -contains $t) { "FOUND   $t" } else { "MISSING $t" }
}
```

### 4. Call chat completions for each target
```powershell
function Try-Chat($model) {
  try {
    $body = @{
      model = $model
      messages = @(@{ role='user'; content='Hello, what can you help me with in one sentence?' })
      temperature = 0.7
      max_tokens = 80
    } | ConvertTo-Json -Depth 6

    $resp = Invoke-RestMethod -Method POST -Uri "$base/chat/completions" -Headers ($headers + @{ 'Content-Type'='application/json' }) -Body $body
    "SUCCESS $model"
    "REPLY   $($resp.choices[0].message.content)"
  } catch {
    $msg = $_.Exception.Message
    if ($_.ErrorDetails.Message) { $msg = $_.ErrorDetails.Message }
    "FAILED  $model"
    "ERROR   $msg"
  }
}

Try-Chat 'nvidia/nemotron-3-super-120b-a12b'
Try-Chat 'nvidia/nemotron-4-340b-instruct'
Try-Chat 'nvidia/llama-3.1-nemotron-70b-instruct'
Try-Chat 'meta/llama-3.1-8b-instruct'
```

## Outputs Observed
- `/v1/models` returned successfully and listed target IDs.
- `nvidia/nemotron-3-super-120b-a12b` returned success.
- `meta/llama-3.1-8b-instruct` returned success.
- `nvidia/nemotron-4-340b-instruct` returned:
  - `404 Not found for account` (account entitlement restriction)
- `nvidia/llama-3.1-nemotron-70b-instruct` returned:
  - `404 Not found for account` (account entitlement restriction)

## Fast Repeat Setup (<2 min)
Use this minimal sequence to validate key + endpoint + one known-good model quickly:

```powershell
$envFile='C:\Users\keith\dev\.env'
$keyLine = Get-Content $envFile | Where-Object { $_ -match '^NVIDIA_API_KEY=' } | Select-Object -First 1
$apiKey = ($keyLine -split '=',2)[1].Trim().Trim('"')
$base='https://integrate.api.nvidia.com/v1'
$headers=@{ Authorization = "Bearer $apiKey"; 'Content-Type'='application/json' }

Invoke-RestMethod -Method GET -Uri "$base/models" -Headers @{ Authorization = "Bearer $apiKey" } | Out-Null

$body = @{
  model = 'meta/llama-3.1-8b-instruct'
  messages = @(@{ role='user'; content='PING_OK' })
  max_tokens = 16
  temperature = 0
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method POST -Uri "$base/chat/completions" -Headers $headers -Body $body
```

## Equivalent Bash Commands (WSL/Linux/macOS)
```bash
BASE="https://integrate.api.nvidia.com/v1"
API_KEY="${NVIDIA_API_KEY}"

curl -sS "$BASE/models" \
  -H "Authorization: Bearer $API_KEY"

curl -sS "$BASE/chat/completions" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model":"meta/llama-3.1-8b-instruct",
    "messages":[{"role":"user","content":"PING_OK"}],
    "temperature":0,
    "max_tokens":16
  }'
```

## Exact Prompt Strings Used by This Agent During Execution
- `Hello, what can you help me with in one sentence?`
- `PING_OK`

## Operational Notes
- Seeing a model in `/v1/models` does not always guarantee invocation entitlement for the current account.
- If chat returns `404 Not found for account`, switch to a model that is both listed and callable (for this account, `meta/llama-3.1-8b-instruct` and `nvidia/nemotron-3-super-120b-a12b` worked).
