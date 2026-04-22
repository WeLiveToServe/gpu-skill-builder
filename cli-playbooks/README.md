# Open-Source CLI Playbooks

Last updated: 2026-04-22

Purpose:
- Track setup, auth, connectivity tests, and runbooks for local open-source coding CLIs.
- Mirror the organization style used in `launch-playbooks` for GPU providers.

Important scope note:
- these files are harness runbooks and benchmark notes
- they are not the root source of truth for provider support in `skill.py`
- historical validations here do not mean the new profile-driven handoff iteration is live-validated; that current iteration is still untested

Current status snapshot:
- `opencode`: exercised and validated for local harness flow with GPU endpoint integration.
- `qwen-code`: validated against DigitalOcean H200 (`google/gemma-4-31B-it`) on 60/80/90 suites.
- `codex-open-source`: validated against DigitalOcean H200 (`google/gemma-4-31B-it`) on 60/80/90 suites.
- `claude-open-source`: validated against DigitalOcean H200 (`google/gemma-4-31B-it`) on 60/80/90 suites.

Direct endpoint vs coding harness summary:
- Confirmed: coding harness can call healthy GPU endpoints by API.
- Confirmed: direct endpoint failures (model load/OOM or account entitlement) propagate to harness unless fallback/provider-switch logic is applied.
- Current readiness contract for new work: prefer endpoints that pass `/health`, `/v1/models`, and a smoke prompt, or call `ensure_active_endpoint()` before a coding run.

Provider advice by harness:
- `opencode`:
  - Validated against `modal` and `nvidia`.
  - Not yet validated against `digitalocean`, `thundercompute`, `vastai`, `huggingface-paid-endpoint`, `huggingface-zerogpu`, `huggingface-spaces`.
- `qwen-code`:
  - Validated against `digitalocean` (Gemma-4 on H200) via OpenAI-compatible endpoint tunnel.
  - Not yet validated against `modal`, `nvidia`, `thundercompute`, `vastai`, `huggingface-paid-endpoint`, `huggingface-zerogpu`, `huggingface-spaces`.
- `codex-open-source`:
  - Validated against `digitalocean` (Gemma-4 on H200) via OpenAI-compatible endpoint tunnel.
  - Not yet validated against `modal`, `nvidia`, `thundercompute`, `vastai`, `huggingface-paid-endpoint`, `huggingface-zerogpu`, `huggingface-spaces`.
- `claude-open-source`:
  - Validated against `digitalocean` (Gemma-4 on H200) via OpenAI-compatible endpoint tunnel.
  - Not yet validated against `modal`, `nvidia`, `thundercompute`, `vastai`, `huggingface-paid-endpoint`, `huggingface-zerogpu`, `huggingface-spaces`.

Folders:
- `opencode`
- `qwen-code`
- `codex-open-source`
- `claude-open-source`
