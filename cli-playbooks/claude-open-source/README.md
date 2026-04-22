# Claude Open-Source CLI

Last updated: 2026-04-22

Current state:
- Validated against live DigitalOcean H200 endpoint serving `google/gemma-4-31B-it`.
- Reproducible suite runner now available: `.bench/run_named_suite.py`.
- This file is a dated benchmark runbook, not a repo-wide provider support matrix.

Provider-specific advice:
- `digitalocean`: validated with claude-open-source through local SSH tunnel (`127.0.0.1:18000 -> <droplet>:8000`).
- `modal`: not yet validated with claude-open-source in this repo cycle.
- `nvidia`: not yet validated with claude-open-source in this repo cycle.
- `thundercompute`: not yet validated with claude-open-source in this repo cycle.
- `vastai`: not yet validated with claude-open-source in this repo cycle.
- `huggingface-paid-endpoint`: not yet validated with claude-open-source in this repo cycle.
- `huggingface-zerogpu`: not yet validated with claude-open-source in this repo cycle.
- `huggingface-spaces`: not yet validated with claude-open-source in this repo cycle.

## Endpoint wiring (Gemma-4 on DO H200)

Validated endpoint:
- model: `google/gemma-4-31B-it`
- API: `http://127.0.0.1:18000/v1` (local tunnel)

Tunnel command:

```powershell
ssh -i "$HOME\.ssh\do_agent_ed25519" -o StrictHostKeyChecking=no -N -L 18000:127.0.0.1:8000 root@<DROPLET_IP>
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

Claude-open-source run command used:

```powershell
$env:BENCH_CLAUDE_MODEL='google/gemma-4-31B-it'
python .\.bench\run_named_suite.py `
  --harness claude `
  --suites medium60,hard80,hard90 `
  --timeout-s 900 `
  --ledger .\.bench\suite_runs_claude_gemma4.json
```

## Results (Claude-open-source + Gemma-4)

Run date: April 18, 2026

- `medium60`: `5/5` pass
- `hard80`: `5/5` pass
- `hard90`: `5/5` pass
- aggregate: `15/15` pass

Artifacts:
- ledger: [suite_runs_claude_gemma4.json](/c:/Users/keith/dev/gpu-skill-builder/.bench/suite_runs_claude_gemma4.json)
- `medium60`: [results.json](/c:/Users/keith/dev/gpu-skill-builder/.bench/benchmark-results/run-1776481086-claude-gemma4-medium60/results.json)
- `hard80`: [results.json](/c:/Users/keith/dev/gpu-skill-builder/.bench/benchmark-results/run-1776481120-claude-gemma4-hard80/results.json)
- `hard90`: [results.json](/c:/Users/keith/dev/gpu-skill-builder/.bench/benchmark-results/run-1776481182-claude-gemma4-hard90/results.json)

Task definitions tracked in:
- [task_suites_registry.json](/c:/Users/keith/dev/gpu-skill-builder/.bench/task_suites_registry.json)

## Extreme100 (Gemma 4B)

Additional stress run with a 20-task `extreme100` suite on `google/gemma-4-E4B-it`:

- suite: `extreme100` (`.bench/harness_benchmark_extreme100.py`)
- result: `5/20` pass
- run artifacts: [results.json](/c:/Users/keith/dev/gpu-skill-builder/.bench/benchmark-results/run-1776482017-claude-gemma4-extreme100/results.json)
- ledger: [suite_runs_claude_gemma4b_extreme100_rerun.json](/c:/Users/keith/dev/gpu-skill-builder/.bench/suite_runs_claude_gemma4b_extreme100_rerun.json)

Observed failure pattern:
- Mostly algorithmic incorrectness or incomplete implementations under extreme task complexity (not transport failures).

What to store here:
- Install/config steps
- Endpoint/provider wiring
- Test prompts and quality evaluation notes
