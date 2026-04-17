# Modal H100 GPT-OSS-120B Deployment Log

Date: 2026-04-17  
Operator: Codex agent  
Workspace: `C:\Users\keith\dev\gpu-skill-builder`

## Goal
Start an H100 Modal app, query model availability, load `openai/gpt-oss-120b`, and deploy.

## Exact User Prompt That Triggered This Run
`launch now`  
`please load it onto the gpu. stop there, I want to understand how to deploy it before you do so`  
`you can deploy it, but please write EXPLICIT LOG of exactly what you did ...`

## Prereqs Used
- `modal` CLI installed and authenticated.
- `MODAL_TOKEN_ID` and `MODAL_TOKEN_SECRET` present in local/shared env.
- Python available in repo venv/system environment.

## Exact Commands Run (PowerShell)

### 1. Verify toolchain
```powershell
$ts=(Get-Date).ToString('yyyy-MM-dd HH:mm:ss zzz'); Write-Output "START_TS=$ts"; modal --version; python --version
```

### 2. Query model availability (OpenCode Zen + Hugging Face)
```powershell
@'
import requests

urls=[
 'https://opencode.ai/zen/v1/models',
 'https://huggingface.co/api/models/openai/gpt-oss-120b'
]
for u in urls:
    try:
        r=requests.get(u, timeout=30)
        print('URL=',u)
        print('STATUS=',r.status_code)
        print('SNIPPET=',r.text[:220].replace('\n',' '))
    except Exception as e:
        print('URL=',u)
        print('ERROR=',e)
'@ | python -
```

```powershell
@'
import requests
u='https://huggingface.co/api/models?search=openai/gpt-oss&limit=10'
r=requests.get(u, timeout=30)
print('STATUS=',r.status_code)
print('BODY=',r.text[:400])
'@ | python -
```

### 3. Deploy H100 + GPT-OSS-120B
```powershell
@'
import asyncio
from modal_bootstrap import deploy_vllm_app

async def main():
    info = await deploy_vllm_app(
        gpu='H100',
        model='openai/gpt-oss-120b',
        app_name='gpu-skill-h100-gpt-oss-120b'
    )
    print('APP_NAME=' + info.app_name)
    print('APP_ID=' + info.app_id)
    print('ENDPOINT=' + info.endpoint_url)
    print('GPU=' + info.gpu)
    print('MODEL=' + info.model)
    print('STATUS=' + info.status)

asyncio.run(main())
'@ | python -
```

### 4. Validate endpoint health
```powershell
@'
import httpx
urls=[
 'https://keith-harmon--gpu-skill-h100-gpt-oss-120b-vllmserver-serve.modal.run/health',
 'https://default--gpu-skill-h100-gpt-oss-120b-vllmserver-serve.modal.run/health'
]
for u in urls:
    try:
        r=httpx.get(u, timeout=25)
        print('URL=',u)
        print('STATUS=',r.status_code)
        print('BODY=',r.text[:160])
    except Exception as e:
        print('URL=',u)
        print('ERROR=',e)
'@ | python -
```

## Outputs Observed
- Deploy succeeded and created Modal app: `gpu-skill-h100-gpt-oss-120b`.
- Modal deployment URL shown in deploy output:
  - `https://keith-harmon--gpu-skill-h100-gpt-oss-120b-vllmserver-serve.modal.run`
- Bootstrap helper returned `default--...` URL fallback, which is not the correct callable endpoint (`404 modal-http: invalid function call`).
- Correct endpoint timed out on `/health` during immediate checks (model likely still warming/initializing).

## Fast Repeat Setup (<2 min command phase)
This is the minimal setup-phase command set (launch + deploy request), excluding model warmup time:

```powershell
cd C:\Users\keith\dev\gpu-skill-builder
@'
import asyncio
from modal_bootstrap import deploy_vllm_app
async def main():
    info = await deploy_vllm_app(gpu='H100', model='openai/gpt-oss-120b', app_name='gpu-skill-h100-gpt-oss-120b')
    print(info.endpoint_url)
asyncio.run(main())
'@ | python -
```

Expected behavior:
- Command returns in ~2 minutes for setup/deploy initiation.
- First model boot can take longer before `/health` is ready.

## Equivalent Bash Commands (WSL/Linux/macOS)
```bash
cd /mnt/c/Users/keith/dev/gpu-skill-builder
python - <<'PY'
import asyncio
from modal_bootstrap import deploy_vllm_app
async def main():
    info = await deploy_vllm_app(gpu="H100", model="openai/gpt-oss-120b", app_name="gpu-skill-h100-gpt-oss-120b")
    print("ENDPOINT=", info.endpoint_url)
asyncio.run(main())
PY
```

## Exact Prompt Strings Used by This Agent During Execution
No interactive LLM prompts were sent to Modal or Hugging Face services.  
Only explicit CLI/API commands above were used.

## Stop Command
```powershell
@'
import asyncio
from modal_bootstrap import stop_app
asyncio.run(stop_app("gpu-skill-h100-gpt-oss-120b"))
'@ | python -
```
