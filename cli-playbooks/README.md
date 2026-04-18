# Open-Source CLI Playbooks

Last updated: 2026-04-18

Purpose:
- Track setup, auth, connectivity tests, and runbooks for local open-source coding CLIs.
- Mirror the organization style used in `launch-playbooks` for GPU providers.

Current status snapshot:
- `opencode`: exercised and validated for local harness flow with GPU endpoint integration.
- `qwen-code`: validated against DigitalOcean H200 (`google/gemma-4-31B-it`) on 60/80/90 suites.
- `codex-open-source`: validated against DigitalOcean H200 (`google/gemma-4-31B-it`) on 60/80/90 suites.
- `claude-open-source`: validated against DigitalOcean H200 (`google/gemma-4-31B-it`) on 60/80/90 suites.

Direct endpoint vs coding harness summary:
- Confirmed: coding harness can call healthy GPU endpoints by API.
- Confirmed: direct endpoint failures (model load/OOM or account entitlement) propagate to harness unless fallback/provider-switch logic is applied.

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
