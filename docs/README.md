# Docs Index

This `docs` tree is the starting point for implementation-ready planning inside `gpu-skill-builder`.

## Research Packages

### Production-Grade GPU Deployment Research Package

Location: [docs/research/production-grade-gpu-deployment](./research/production-grade-gpu-deployment)

Recommended reading order:

1. [Executive Summary](./research/production-grade-gpu-deployment/EXECUTIVE_SUMMARY.md)
2. [Main Report](./research/production-grade-gpu-deployment/MAIN_REPORT.md)
3. [Deployment Checklists and Launch Recipes](./research/production-grade-gpu-deployment/DEPLOYMENT_CHECKLISTS.md)
4. [Implementation Work Items](./research/production-grade-gpu-deployment/IMPLEMENTATION_WORK_ITEMS.md)
5. [Package Recommendations](./research/production-grade-gpu-deployment/PACKAGE_RECOMMENDATIONS.md)
6. [Adoption Roadmap](./research/production-grade-gpu-deployment/ADOPTION_ROADMAP.md)
7. [Model/Provider/Runtime Matrix](./research/production-grade-gpu-deployment/MODEL_PROVIDER_RUNTIME_MATRIX.json)

## What Each Document Is For

- [Executive Summary](./research/production-grade-gpu-deployment/EXECUTIVE_SUMMARY.md)
  Best provider path per model, minimum viable deployment, production-safe deployment, testing-only paths, and clear "do not attempt" calls.
- [Main Report](./research/production-grade-gpu-deployment/MAIN_REPORT.md)
  The detailed technical report covering providers, model families, long-context serving, parallelism, skills-heavy workloads, and rationale.
- [Deployment Checklists and Launch Recipes](./research/production-grade-gpu-deployment/DEPLOYMENT_CHECKLISTS.md)
  Exact operator-facing deployment sequence, acceptance gates, rollback flow, and conservative `vLLM` launch recipes.
- [Implementation Work Items](./research/production-grade-gpu-deployment/IMPLEMENTATION_WORK_ITEMS.md)
  Issue-sized repo work items with exact touch points, acceptance criteria, and suggested execution order.
- [Package Recommendations](./research/production-grade-gpu-deployment/PACKAGE_RECOMMENDATIONS.md)
  Concrete package review for serving, observability, devops continuity, and evals, with `Adopt now`, `Prototype`, `Track only`, and `Avoid` classifications.
- [Adoption Roadmap](./research/production-grade-gpu-deployment/ADOPTION_ROADMAP.md)
  The recommended implementation order for turning the research package into durable repo changes.
- [Model/Provider/Runtime Matrix](./research/production-grade-gpu-deployment/MODEL_PROVIDER_RUNTIME_MATRIX.json)
  Machine-readable source-of-truth draft for resolved model targets, provider classifications, runtime choices, and recommended conservative profiles.

## Current Posture

The material in this docs tree is intentionally conservative. It is optimized for:

- stable `128k` operation
- skills-heavy agent workloads
- provider choices that can hold up tomorrow
- implementation sequencing that avoids unnecessary platform churn
