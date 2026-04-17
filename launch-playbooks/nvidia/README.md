# NVIDIA Playbooks

Last updated: 2026-04-17

Current state:
- NVIDIA hosted endpoint connectivity is validated using `https://integrate.api.nvidia.com/v1`.
- Verified callable models in this account: `meta/llama-3.1-8b-instruct`, `nvidia/nemotron-3-super-120b-a12b`.
- Observed account-level invocation failures (`404 not found for account`) for:
  - `nvidia/nemotron-4-340b-instruct`
  - `nvidia/llama-3.1-nemotron-70b-instruct`

Direct endpoint vs coding harness notes:
- Direct endpoint checks:
  - Success on callable models above using `/v1/chat/completions`.
  - Failure on non-entitled models even when listed by `/v1/models`.
- Coding harness path:
  - Not yet validated for NVIDIA in this repo cycle.
  - Expected behavior: once wired into provider config, harness should call the same endpoint and inherit the same model entitlement constraints.

Runbooks:
- `NVIDIA_ENDPOINT_NEMOTRON_PLAYBOOK.md`: exact endpoint validation and Nemotron invocation procedure (PowerShell + Bash), including observed success/failure cases.
