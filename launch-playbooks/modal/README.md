# Modal Launches

Last updated: 2026-04-17

Current state:
- Modal connectivity and deployment flow are validated.
- `openai/gpt-oss-120b` launch was attempted on H100 but failed to become healthy due to model load/OOM behavior.
- `Qwen/Qwen3-8B` was successfully deployed and endpoint-tested on H100.
- The last active Modal test instance was intentionally stopped (no active instance expected right now).

Direct endpoint vs coding harness notes:
- Direct endpoint checks:
  - `gpt-oss-120b` deployment endpoint did not become healthy (warmup/load/OOM path).
  - `Qwen3-8B` endpoint health/models checks succeeded when instance was active.
- Coding harness path (OpenCode -> provider -> Modal endpoint):
  - Worked when pointed at a healthy deployed model (`Qwen3-8B`).
  - Produced code output via harness API; quality varied by model/prompt, but connectivity was confirmed.

Runbooks:
- `H100_GPT_OSS_120B_DEPLOY_LOG.md`: full command log for H100 + `openai/gpt-oss-120b` deployment attempt.
