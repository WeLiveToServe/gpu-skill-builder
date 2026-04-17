# Open-Source CLI Playbooks

Last updated: 2026-04-17

Purpose:
- Track setup, auth, connectivity tests, and runbooks for local open-source coding CLIs.
- Mirror the organization style used in `launch-playbooks` for GPU providers.

Current status snapshot:
- `opencode`: exercised and validated for local harness flow with GPU endpoint integration.
- `qwen-code`: not yet run in this repo cycle.
- `codex-open-source`: not yet run in this repo cycle.
- `claude-open-source`: not yet run in this repo cycle.

Direct endpoint vs coding harness summary:
- Confirmed: coding harness can call healthy GPU endpoints by API.
- Confirmed: direct endpoint failures (model load/OOM or account entitlement) propagate to harness unless fallback/provider-switch logic is applied.

Folders:
- `opencode`
- `qwen-code`
- `codex-open-source`
- `claude-open-source`
