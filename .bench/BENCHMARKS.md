# CLI Coding Benchmark Harness

Evaluates four CLI agents (claude, codex, opencode, qwen) against Python coding tasks of varying difficulty. Each agent runs in an isolated temp directory so it cannot touch the main repo.

## Agents

| Harness | CLI | Protocol |
|---------|-----|----------|
| `claude` | claude-code | Anthropic API (JSON output) |
| `codex` | codex | OpenAI-compatible (responses API) |
| `opencode` | opencode | OpenAI-compatible (pure mode) |
| `qwen` | qwen-code | OpenAI-compatible (JSON output) |
| `goose` | goose | OpenAI-compatible via `OPENAI_HOST` + `--quiet` |

## Task Suites

| Suite ID | Difficulty | Tasks | Module |
|----------|------------|-------|--------|
| `medium60` | ~60/100 | 5 | `harness_benchmark.py` |
| `hard80` | ~80/100 | varies | `harness_benchmark_hard_opencode.py` |
| `hard90` | ~90/100 | varies | `harness_benchmark_hard90_opencode.py` |
| `hard90_v2` | ~90/100 | varies | `harness_benchmark_hard90_v2.py` |
| `extreme100` | ~100/100 | varies | `harness_benchmark_extreme100.py` |

## Prerequisites

The model server must be running and reachable before launching the harness. Configure endpoints and CLI paths via environment variables:

```bash
export BENCH_OPENAI_BASE_URL=https://openrouter.ai/api/v1  # default
export BENCH_ANTHROPIC_BASE_URL=https://openrouter.ai/api  # default
export BENCH_CLAUDE_MODEL=qwen/qwen3.6-plus                # default
export BENCH_CODEX_MODEL=qwen/qwen3.6-plus                 # default
export BENCH_OPENCODE_MODEL=openrouter/qwen/qwen3.6-plus   # default
export BENCH_QWEN_MODEL=qwen/qwen3.6-plus                  # default

# Optional: override CLI paths (defaults to %APPDATA%/npm/*.cmd)
export BENCH_CLAUDE_CLI=/path/to/claude.cmd
export BENCH_CODEX_CLI=/path/to/codex.cmd
export BENCH_OPENCODE_CLI=/path/to/opencode.cmd
export BENCH_QWEN_CLI=/path/to/qwen.cmd

# Goose runner (install binary first: run download_cli.ps1 in goose repo)
# Defaults to ~/.local/bin/goose (or goose.exe on Windows)
export BENCH_GOOSE_CLI=~/.local/bin/goose
export BENCH_GOOSE_MODEL=<model-id>   # same model ID as other runners
```

Codex compatibility note:
- `run_codex()` already applies OpenRouter-safe `--disable` flags (`apps`, `plugins`, `personality`, `multi_agent`, `skill_mcp_dependency_install`, `tool_suggest`, `workspace_dependencies`) by default.

Local GPU benchmark note:
- A new DigitalOcean H200 matrix orchestrator lives at `.bench/run_do_h200_extreme100_matrix.py`.
- It temporarily relaunches the current droplet in clean `gpt-oss-120b` benchmark mode, opens a local tunnel, runs `codex -> claude -> qwen -> opencode`, and restores the original interactive service by default.
- This orchestration path is implemented but still untested end-to-end until we run the real remote job.

**Goose binary:** Install from the goose repo before using the goose harness:
```powershell
# In C:/Users/keith/dev/goose/
.\download_cli.ps1
# Installs to %USERPROFILE%\.local\bin\goose.exe
```

## Running

**Single harness, one or more suites:**
```bash
cd .bench
python run_named_suite.py --harness claude --suites medium60,hard90
```

**With a ledger file (tracks run metadata):**
```bash
python run_named_suite.py --harness codex --suites medium60,hard80,hard90 \
  --ledger suite_runs_codex_latest.json
```

**Run a subset with explicit artifact labeling:**
```bash
python run_named_suite.py --harness codex --suites extreme100 \
  --task-ids x100_01_max_flow_dinic,x100_02_min_cost_max_flow \
  --run-label smoke10 \
  --ledger suite_runs_codex_smoke10.json
```

**Run the DO H200 local-GPU matrix:**
```bash
python run_do_h200_extreme100_matrix.py
```

**Full matrix (all agents × all suites)** — run once per harness:
```bash
for h in claude codex opencode qwen goose; do
  python run_named_suite.py --harness $h --suites medium60,hard80,hard90,extreme100 \
    --ledger suite_runs_${h}_latest.json
done
```

## Artifacts

Results land in `benchmark-results/run-<timestamp>-<harness>-<model>-<suite-or-label>/`:

```
run-<ts>-claude-gemma4-hard90/
  results.json          ← pass/fail per task + config snapshot
  raw/<harness>/        ← raw stdout/stderr per task
  parsed/<harness>/     ← extracted response text + parsed code (.code.py)
```

`benchmark-results/` and `suite_runs_*.json` ledgers are gitignored — only harness code and config are committed.

## Isolation

Each agent subprocess runs from a throwaway `tempfile.TemporaryDirectory()` so it cannot read or write files in the repo. Codex's `-C` flag and Claude's working directory both point to the temp dir, not the project root.
