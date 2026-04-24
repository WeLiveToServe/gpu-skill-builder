# Benchmarks Reference

Use this reference when changing `.bench/`, benchmark profiles, local-GPU endpoint overrides, benchmark result handling, or matrix orchestration.

## Runtime Truth

- Root README benchmark section
- Benchmark code under `.bench/`
- CLI wrapper behavior in `open_harness_common.py` and harness-specific wrappers
- Benchmark-safe runtime profiles under `profiles/deployments/`
- README consistency tests

Benchmark artifacts, ledgers, logs, probe output, and matrix-run backups are intentionally ignored unless a specific artifact is promoted to documentation.

## Supported Modes

- OpenRouter/default mode uses normal OpenRouter configuration.
- Local-GPU mode uses process-scoped `HARNESS_OPENROUTER_BASE_URL`, `HARNESS_OPENROUTER_MODEL`, and `HARNESS_OPENROUTER_API_KEY` overrides.

The DigitalOcean H200 `extreme100` matrix runner is implemented and locally dry-run, but the root README currently says it has not been validated end-to-end against the live H200 matrix.

## H200 Matrix Invariant

The matrix runner should preserve the operator's existing remote service by backing up the current `vllm.service` and env file, launching the benchmark-safe `harness-eval` profile, opening a local tunnel, running the harness sequence, and restoring the original interactive service by default.

## Change Rules

- Use explicit committed deployment profiles for benchmark-safe settings.
- Keep benchmark-specific environment overrides process-scoped.
- Do not write benchmark endpoint settings into sibling harness repos.
- Update root README caveats only after actual live validation has happened.
- For orchestration changes, prefer dry-run and focused tests before any live GPU matrix execution.
