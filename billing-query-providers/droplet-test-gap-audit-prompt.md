You are a senior software test architect.

Task: Perform a massive test-gap audit for exactly two repositories:
1) qwen-code
2) gpu-skill-builder

You are preparing actionable backlog output for a human+agent team.

Important constraints:
- Focus on finding missing tests, risky untested behaviors, likely regressions, and weakest confidence areas.
- Prioritize by risk and impact.
- Do not suggest generic "add more tests" bullets.
- Prefer precise, PR-sized tasks with clear target areas.
- Assume these are active repos with some existing tests and mixed maturity.

Repo context (from local inventory):

qwen-code:
- Purpose: terminal AI agent optimized for Qwen models; multi-protocol/provider support.
- Top-level dirs include: docs, docs-site, eslint-rules, integration-tests, packages, scripts, dist.
- Tech signals: Node/TypeScript monorepo, vitest config present.
- Risks likely include provider routing, protocol compatibility, tool orchestration, CLI interaction, integration behavior.

gpu-skill-builder:
- Purpose: agent-callable GPU provisioning skill that creates OpenAI-compatible endpoints with TTL/watchdog/cost guardrails.
- Top-level dirs/files include: providers/, modal_apps/, create_droplet.py, do_bootstrap.py, modal_bootstrap.py, scheduler.py, skill.py, models.py, config.py, main.py.
- Billing scripts now include billing-query-providers/digitalocean_billing_query.py and tracking docs.
- Risks likely include lifecycle safety (TTL/delete), stuck pending handling, idempotency/cost controls, provider API edge cases, state handling.

Deliverables (strict format):

A) Executive risk summary
- Max 12 bullets, ordered high->low risk.

B) Detailed gap matrix
- Markdown table with columns:
  Repo | Risk Area | Missing Test Scenario | Why It Matters | Suggested Test Type | Priority (P0/P1/P2) | Effort (S/M/L)
- At least 30 rows total across both repos.

C) First implementation wave
- Exactly 20 PR-sized test tasks, each with:
  - Title
  - Target module/path (best estimate)
  - Test outline (inputs/actions/assertions)
  - Dependencies/blockers
  - Acceptance criteria
- Keep each task independently shippable.

D) Minimal sequencing plan
- 3 phases (Stabilize, Expand, Harden)
- Each phase should list concrete outcomes and measurable exit criteria.

E) "Unknowns to confirm quickly"
- Up to 12 items that need fast validation from maintainers before coding.

Tone:
- Concrete, tactical, high-signal.
- No fluff.
