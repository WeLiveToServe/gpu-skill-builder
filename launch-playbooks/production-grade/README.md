# Production-Grade Playbooks

This folder contains **draft planning artifacts** derived from the `production-grade-gpu-deployment` research package.

Current repo boundary:

- canonical runtime profiles now live under the repo-root `profiles/` directory
- this folder is still draft planning/reference material
- the current profile-driven runtime iteration is still untested on live providers and harnesses

What these files are for today:

- manifest drafts for conservative `128k` deployment profiles
- a reusable Linux `systemd` template for self-hosted `vLLM`
- an example env file that matches the template

What these files are not:

- they are not parsed directly by provider code
- they are not the canonical runtime config source
- they are not a promise that every listed provider/model pair is implemented or production-ready

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

Planning posture:

- `gpt-oss-120b` is the cleanest single-node self-host target.
- `Qwen3-Coder-480B`, `DeepSeek-V3.1`, and `MiniMax-M2.7` are treated as `8x H200` class deployments.
- `Kimi-K2` remains managed-first; any self-host artifact here is R&D-only.
- NVIDIA managed validation remains outside the self-host manifest set because the low-level runtime knobs are not exposed there.
