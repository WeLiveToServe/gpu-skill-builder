# Adoption Roadmap For gpu-skill-builder

This roadmap turns the package matrix into an implementation order that is ambitious but durable. The main policy is simple: do not turn `gpu-skill-builder` into a platform rewrite before the core deployment story is stable.

## Companion Documents

- [Main Report](./MAIN_REPORT.md)
- [Executive Summary](./EXECUTIVE_SUMMARY.md)
- [Deployment Checklists and Launch Recipes](./DEPLOYMENT_CHECKLISTS.md)
- [Implementation Work Items](./IMPLEMENTATION_WORK_ITEMS.md)
- [Model/Provider/Runtime Matrix](./MODEL_PROVIDER_RUNTIME_MATRIX.json)
- [Package Recommendations](./PACKAGE_RECOMMENDATIONS.md)


## Working Principle

Adopt the packages that improve correctness, visibility, and repeatability first. Prototype the packages that help with giant MoE edge cases only after the default `vLLM` path is boringly reliable.

## The Order That Makes Sense

### Phase 0: Lock The Deployment Contract

Target window: `1-2 days`

Goals:

- Make the research package the written source of truth.
- Define one canonical deployable target per model family.
- Define one conservative runtime profile per target model.
- Define one provider recommendation per model for:
  - minimum viable
  - production-safe
  - testing only

Concrete deliverables:

- model family mapping table in repo docs or config
- canonical runtime profile document for:
  - `gpt-oss-120b`
  - `Qwen3-Coder-480B`
  - `DeepSeek-V3.1`
  - `MiniMax-M2.7`
  - `Kimi-K2`
- explicit rule that `128k` defaults are conservative and not tuned for peak throughput

Exit criteria:

- every target model has one default provider path
- every target model has one fallback path
- nobody on the team has to guess which model name or runtime profile is canonical

### Phase 1: Adopt The Core Package Set

Target window: `week 1`

Packages:

- `vllm`
- `prometheus-client`
- `opentelemetry-sdk`
- `opentelemetry-instrumentation-httpx`
- `opentelemetry-instrumentation-fastapi`
- `nvidia-ml-py`
- `inspect-ai`
- `lm-evaluation-harness`

Why this comes first:

- It hardens the existing deployment shape instead of replacing it.
- It gives immediate visibility into health, latency, retries, and GPU state.
- It gives you both model evals and harness evals without waiting for a larger platform change.

Implementation themes:

- widen the surfaced `vLLM` policy knobs
- instrument provider calls and deployment phases
- expose machine-readable GPU health
- stand up repeatable model and harness evaluation entry points

Exit criteria:

- deployment logs and metrics answer "what failed?" without guesswork
- GPU memory pressure is visible from the control plane
- every supported model family has a standard smoke-eval path
- every harness path has a standard tool-call correctness path

### Phase 2: Add Continuity And Safe Rollouts

Target window: `week 2`

Main moves:

- standardize `systemd` service templates for model serving
- standardize health/readiness and restart policy
- standardize rollback inputs:
  - image version
  - model revision
  - runtime profile
- add deployment acceptance gates that must pass before a node is marked usable

Suggested repo outputs:

- deployment manifest format
- provider-specific systemd template files
- health probe policy
- rollout and rollback checklist docs

Why this is phase 2:

- Observability without rollout discipline still leaves you doing fragile repairs by hand.
- This phase makes continuity real without forcing a large new dependency graph.

Exit criteria:

- cold start is repeatable
- restart is repeatable
- rollback is repeatable
- health and readiness have the same meaning across providers

### Phase 3: Prototype The High-Leverage Optional Tools

Target window: `week 3`

Packages:

- `sglang`
- `litellm`
- `lighteval`
- `dcgm-exporter`
- `locust`
- `ansible-core`

Prototype order:

1. `SGLang`
   Test it only on `DeepSeek` and `Kimi` class models where MoE behavior may justify the extra runtime path.
2. `LiteLLM`
   Test it as a gateway above existing endpoints, not as a replacement for provider orchestration.
3. `dcgm-exporter`
   Add it on self-hosted GPU nodes once Prometheus-style monitoring exists.
4. `Locust`
   Use it for repeatable endpoint load and tail-latency tests after smoke tests are already solid.
5. `Ansible`
   Adopt only when the deployment footprint becomes large enough that shell-driven rollout is too brittle.
6. `Lighteval`
   Add it only if you need the additional HF-oriented eval surface beyond `inspect-ai` plus `lm-evaluation-harness`.

Exit criteria:

- at least one prototype clearly proves its value
- no prototype becomes mandatory until it reduces pain more than it adds complexity

### Phase 4: Separate Control Plane From Inference Plane

Target window: `week 4+`

Goal:

Make `gpu-skill-builder` better at orchestrating inference than at living on the same box as inference.

What to do:

- keep orchestration and eval coordination on cheaper CPU/control-plane hosts
- keep inference nodes focused on serving
- route metrics, traces, and health events back to the control plane
- make provider differences explicit in the control layer instead of hiding them in ad hoc shell branches

Why it matters:

- skills-heavy workloads create a lot of non-inference work
- you do not want tracing, evaluation, and orchestration competing with giant models for the same box

Exit criteria:

- the control plane can survive inference node restarts
- evals continue to run even when a specific model node is replaced
- operator workflows are the same whether the GPU host is DigitalOcean or Oracle

### Phase 5: Cluster Features, Not Before

Target window: `later`

Only after the earlier phases are stable should you invest in:

- multi-node long-context cluster tuning
- deeper expert-parallel and context-parallel experiments
- model-family-specific alternate runtimes for giant MoE deployments
- broader rollback and image-promotion automation

This is where `Kimi` becomes a serious engineering lane rather than a hopeful prototype.

## Recommended Package Decisions

### Adopt now

- `vllm`
- `prometheus-client`
- `opentelemetry-sdk`
- `opentelemetry-instrumentation-httpx`
- `opentelemetry-instrumentation-fastapi`
- `nvidia-ml-py`
- `inspect-ai`
- `lm-evaluation-harness`

### Prototype

- `sglang`
- `litellm`
- `lighteval`
- `dcgm-exporter`
- `locust`
- `ansible-core`
- `nvitop`

### Track only

- `text-generation-inference`
- `ansible-runner`
- `tensorRT-LLM`

### Avoid for now

- `ray[serve]`

## What "Week 1 / Week 2 / Later" Means In Practice

### Week 1

- make runtime knobs explicit
- add metrics and tracing
- add GPU health visibility
- add baseline model evals
- add baseline harness evals

### Week 2

- standardize service templates
- standardize health/readiness
- standardize rollout and rollback
- make acceptance gates mandatory

### Later

- alternate runtimes
- gateway/routing layer
- full host automation
- multi-node cluster specialization

## What Not To Do

- Do not add three alternate runtimes at once.
- Do not introduce a complex orchestrator before the single-node story is stable.
- Do not optimize for peak concurrency before you can explain every restart and OOM.
- Do not let model naming drift between docs, configs, and deployment scripts.
- Do not make Kimi the first proof point for a new deployment system.

## Recommended First Buildout

If you want the smallest number of moves that most improve the repo, the first concrete buildout should be:

1. widen the `vLLM` configuration surface
2. add metrics and tracing
3. add NVML-backed GPU state collection
4. add `inspect-ai` for harness and tool-call evals
5. add `lm-evaluation-harness` for model regressions
6. standardize rollout, readiness, and rollback

That sequence strengthens the current architecture instead of fighting it.
