# Production-Grade Playbooks

This folder contains implementation-ready draft artifacts derived from the `production-grade-gpu-deployment` research package.

What these files are for:

- manifest drafts for conservative `128k` deployment profiles
- a reusable Linux `systemd` template for self-hosted `vLLM`
- an example env file that matches the template

What these files are not yet:

- they are not wired into `remote_vllm.py`
- they are not yet parsed by provider code
- they are not a promise that every listed provider/model pair is production-ready

Reading order:

1. `docs/research/production-grade-gpu-deployment/EXECUTIVE_SUMMARY.md`
2. `docs/research/production-grade-gpu-deployment/DEPLOYMENT_CHECKLISTS.md`
3. `docs/research/production-grade-gpu-deployment/IMPLEMENTATION_WORK_ITEMS.md`
4. this folder

Folder layout:

- `manifests/`
  Draft deployment manifests for the recommended or explicitly flagged profiles.
- `systemd/`
  Reusable service template for Linux hosts serving `vLLM`.
- `env/`
  Example environment file consumed by the service template.

Current policy:

- `gpt-oss-120b` is the cleanest single-node self-host target.
- `Qwen3-Coder-480B`, `DeepSeek-V3.1`, and `MiniMax-M2.7` are treated as `8x H200` class deployments.
- `Kimi-K2` remains managed-first; any self-host artifact here is R&D-only.
- NVIDIA managed validation remains outside the self-host manifest set because the low-level runtime knobs are not exposed there.
