# Qwen-Code CLI

Last updated: 2026-04-18

Current state:
- Validated against live DigitalOcean H200 endpoint serving `google/gemma-4-31B-it`.
- Reproducible suite runner now available: `.bench/run_named_suite.py`.

Provider-specific advice:
- `digitalocean`: validated with qwen-code through local SSH tunnel (`127.0.0.1:18000 -> <droplet>:8000`).
- `modal`: not yet validated with qwen-code in this repo cycle.
- `nvidia`: not yet validated with qwen-code in this repo cycle.
- `thundercompute`: not yet validated with qwen-code in this repo cycle.
- `vastai`: not yet validated with qwen-code in this repo cycle.
- `huggingface-paid-endpoint`: not yet validated with qwen-code in this repo cycle.
- `huggingface-zerogpu`: not yet validated with qwen-code in this repo cycle.
- `huggingface-spaces`: not yet validated with qwen-code in this repo cycle.

## Endpoint wiring (Gemma-4 on DO H200)

Validated endpoint:
- model: `google/gemma-4-31B-it`
- API: `http://127.0.0.1:18000/v1` (local tunnel)

Tunnel command:

```powershell
ssh -i "$HOME\.ssh\do_agent_ed25519" -o StrictHostKeyChecking=no -N -L 18000:127.0.0.1:8000 root@165.245.137.40
```

Model check:

```powershell
curl.exe -sS http://127.0.0.1:18000/v1/models
```

## Suite runner

Script:
- `.bench/run_named_suite.py`

Supported suite IDs:
- `medium60`
- `hard80`
- `hard90`
- `hard90_v2`

Qwen-code run command used:

```powershell
$env:BENCH_QWEN_MODEL='google/gemma-4-31B-it'
python .\.bench\run_named_suite.py `
  --harness qwen `
  --suites medium60,hard80,hard90 `
  --timeout-s 900 `
  --ledger .\.bench\suite_runs_qwen_gemma4.json
```

## Results (Qwen-code + Gemma-4)

Run date: April 18, 2026

- `medium60`: `5/5` pass
- `hard80`: `4/5` pass
- `hard90`: `5/5` pass
- aggregate: `14/15` pass

Known failure:
- `hard80` -> `hard3_shortest_superstring`
  - returned non-optimal length for `['abcd', 'bc', 'cdef']` (got length `8`, expected `6`).

Artifacts:
- ledger: [suite_runs_qwen_gemma4.json](/c:/Users/keith/dev/gpu-skill-builder/.bench/suite_runs_qwen_gemma4.json)
- `medium60`: [results.json](/c:/Users/keith/dev/gpu-skill-builder/.bench/benchmark-results/run-1776480748-qwen-gemma4-medium60/results.json)
- `hard80`: [results.json](/c:/Users/keith/dev/gpu-skill-builder/.bench/benchmark-results/run-1776480807-qwen-gemma4-hard80/results.json)
- `hard90`: [results.json](/c:/Users/keith/dev/gpu-skill-builder/.bench/benchmark-results/run-1776480886-qwen-gemma4-hard90/results.json)

Task definitions tracked in:
- [task_suites_registry.json](/c:/Users/keith/dev/gpu-skill-builder/.bench/task_suites_registry.json)

What to store here:
- Install/auth steps
- Model/provider mapping
- Validation task logs
