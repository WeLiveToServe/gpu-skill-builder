# Codex Open-Source CLI

Last updated: 2026-04-18

Current state:
- Validated against live DigitalOcean H200 endpoint serving `google/gemma-4-31B-it`.
- Reproducible suite runner now available: `.bench/run_named_suite.py`.

Provider-specific advice:
- `digitalocean`: validated with Codex-OS through local SSH tunnel (`127.0.0.1:18000 -> <droplet>:8000`).
- `modal`: not yet validated with codex-open-source in this repo cycle.
- `nvidia`: not yet validated with codex-open-source in this repo cycle.
- `thundercompute`: not yet validated with codex-open-source in this repo cycle.
- `vastai`: not yet validated with codex-open-source in this repo cycle.
- `huggingface-paid-endpoint`: not yet validated with codex-open-source in this repo cycle.
- `huggingface-zerogpu`: not yet validated with codex-open-source in this repo cycle.
- `huggingface-spaces`: not yet validated with codex-open-source in this repo cycle.

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

Codex-OS run command used:

```powershell
$env:BENCH_CODEX_MODEL='google/gemma-4-31B-it'
python .\.bench\run_named_suite.py `
  --harness codex `
  --suites medium60,hard80,hard90 `
  --timeout-s 900 `
  --ledger .\.bench\suite_runs_codex_gemma4.json
```

## Results (Codex-OS + Gemma-4)

Run date: April 18, 2026

- `medium60`: `5/5` pass
- `hard80`: `5/5` pass
- `hard90`: `5/5` pass
- aggregate: `15/15` pass

Artifacts:
- ledger: [suite_runs_codex_gemma4.json](/c:/Users/keith/dev/gpu-skill-builder/.bench/suite_runs_codex_gemma4.json)
- `medium60`: [results.json](/c:/Users/keith/dev/gpu-skill-builder/.bench/benchmark-results/run-1776480403-codex-gemma4-medium60/results.json)
- `hard80`: [results.json](/c:/Users/keith/dev/gpu-skill-builder/.bench/benchmark-results/run-1776480433-codex-gemma4-hard80/results.json)
- `hard90`: [results.json](/c:/Users/keith/dev/gpu-skill-builder/.bench/benchmark-results/run-1776480481-codex-gemma4-hard90/results.json)

Task definitions tracked in:
- [task_suites_registry.json](/c:/Users/keith/dev/gpu-skill-builder/.bench/task_suites_registry.json)

## Extreme100 (Gemma 4B)

Additional stress run with a 20-task `extreme100` suite on `google/gemma-4-E4B-it`:

- suite: `extreme100` (`.bench/harness_benchmark_extreme100.py`)
- result: `1/20` pass
- run artifacts: [results.json](/c:/Users/keith/dev/gpu-skill-builder/.bench/benchmark-results/run-1776482184-codex-gemma4-extreme100/results.json)
- ledger: [suite_runs_codex_gemma4b_extreme100_rerun.json](/c:/Users/keith/dev/gpu-skill-builder/.bench/suite_runs_codex_gemma4b_extreme100_rerun.json)

Observed failure pattern:
- Many responses were non-compliant with strict code-only format (syntax parse failures during evaluation), plus several partial/incorrect algorithm outputs.

What to store here:
- Installation and environment setup
- Provider integration instructions
- End-to-end coding task validation notes
