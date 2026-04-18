# OpenCode CLI

Last updated: 2026-04-17

Current state:
- OpenCode local harness flow has been exercised from this machine.
- OpenCode server mode was used with provider wiring to GPU-backed endpoints.

Direct endpoint vs coding harness notes:
- Direct GPU/model endpoint:
  - Works only when the underlying model endpoint is healthy and entitled.
  - Failed in prior Modal tests when the model itself failed to load (`gpt-oss-120b` OOM/unhealthy path).
- Through OpenCode coding harness:
  - Connectivity and end-to-end request/response were confirmed when pointing to healthy endpoints (for example Modal `Qwen3-8B` during active run).
  - Harness execution quality is model-dependent; transport and integration path are functioning.

Provider-specific advice:
- `modal`:
  - Works when endpoint is healthy.
  - Verify `/health` and `/v1/models` before coding runs.
  - Known failure path in this repo: model boot/load failure (`gpt-oss-120b`) caused harness failures.
- `nvidia`:
  - Works via OpenAI-compatible wiring in OpenCode.
  - Best reliability observed: `meta/llama-3.1-8b-instruct`.
  - Mixed reliability observed: `nemotron-3-super-120b-a12b` on coding prompts.
  - Ensure API key is bound for outbound auth or requests fail with `401`.
- `digitalocean`: not yet validated in OpenCode for this repo cycle.
- `thundercompute`: not yet validated in OpenCode for this repo cycle.
- `vastai`: not yet validated in OpenCode for this repo cycle.
- `huggingface-paid-endpoint`: not yet validated in OpenCode for this repo cycle.
- `huggingface-zerogpu`: not yet validated in OpenCode for this repo cycle.
- `huggingface-spaces`: not yet validated in OpenCode for this repo cycle.

What to store here:
- Install and upgrade commands
- Provider/base URL config examples
- Connectivity/test transcripts
