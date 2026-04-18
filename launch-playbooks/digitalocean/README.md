# DigitalOcean Launches

Last updated: 2026-04-18

Current state:
- Active H200 droplet confirmed: `165.245.137.40` (`qwen25-7b-h200`).
- Active model now serving: `google/gemma-4-31B-it` on port `8000`.

What this folder is for:
- Store DigitalOcean GPU/droplet launch instructions and verified command logs.

## Deterministic model swap (vLLM on DO)

Use [swap-vllm-model.ps1](swap-vllm-model.ps1) to safely replace the currently served model on an existing droplet.

Default behavior:
- resolves host IP from `.do_state.json` (or accepts `-HostIp`)
- stops existing `vllm` listeners and processes on the API port
- rewrites `/etc/systemd/system/vllm.service` with target model
- restarts `vllm.service`
- health-checks `/health`
- validates `/v1/models` contains the target model ID

Example:

```powershell
.\launch-playbooks\digitalocean\swap-vllm-model.ps1 `
  -HostIp 165.245.137.40 `
  -ModelId google/gemma-4-31B-it `
  -SshKeyPath "$HOME\.ssh\do_agent_ed25519" `
  -Port 8000 `
  -GpuMemoryUtilization 0.92
```

Verified result (2026-04-18 UTC):
- `vllm.service` active
- `/v1/models` includes `google/gemma-4-31B-it`
- `/v1/chat/completions` returns successful completion

Coding harness advice:
- `opencode`: no validated DO endpoint run in this repo yet; once DO endpoint is healthy, wire it as OpenAI-compatible provider (`baseURL` + `apiKey`) and test `/global/health` + one coding prompt.
- `qwen-code`: not yet validated against DigitalOcean.
- `codex-open-source`: not yet validated against DigitalOcean.
- `claude-open-source`: not yet validated against DigitalOcean.
