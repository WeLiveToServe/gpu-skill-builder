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

What to store here:
- Install and upgrade commands
- Provider/base URL config examples
- Connectivity/test transcripts
