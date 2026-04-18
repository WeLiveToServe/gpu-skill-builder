# Claude Handoff — Goose Integration Plan

**Date:** 2026-04-17  
**From:** VS Code Claude Code session  
**To:** CLI Claude Code session (`--dangerously-skip-permissions`)  
**Repo:** `C:/Users/keith/dev/gpu-skill-builder`  
**Goose repo:** `C:/Users/keith/dev/goose` (already cloned)

---

## Context: What Was Just Decided

The user evaluated `https://github.com/aaif-goose/goose` (cloned locally) against this project and wants to pursue integration. Three opportunities were identified, prioritized as follows:

### Priority 1 — GPU-Skill-Builder as a Goose MCP Tool (DO THIS FIRST)
### Priority 2 — Add Goose as a 5th Benchmark Runner in .bench/
### Priority 3 — Open Model Gym Backend Integration (future)

This handoff covers Priority 1 and Priority 2 in detail.

---

## What Goose Is (Key Facts)

- **Language:** Rust (core), TypeScript (SDK bindings)
- **What it does:** General-purpose AI agent framework — CLI + desktop + API server
- **NOT a harness** — it is a runner (agent under test). The harness is the Python `.bench/` system.
- **Key capability relevant here:** Native `openai_compatible.rs` provider — any `/v1/chat/completions` endpoint works as a backend with just `base_url` + `api_key` + `model`
- **Extension system:** MCP-native. Extensions are loaded as stdio subprocesses or HTTP servers exposing MCP tools.
- **Skills system:** Loads `.md` files with YAML frontmatter from `~/.config/goose/skills/` or local paths
- **Config:** `~/.config/goose/config.yaml`

Goose extension loading config format:
```yaml
extensions:
  my_extension:
    type: stdio
    cmd: python
    args: [/path/to/server.py]
    envs: {}
```

---

## Priority 1: GPU-Skill-Builder as a Goose MCP Tool

### What to Build

A Python MCP stdio server (`goose_skill_server.py` at repo root) that:
1. Speaks the MCP protocol over stdin/stdout
2. Exposes one tool: `gpu_provision`
3. Calls the existing `run_skill()` internally
4. Returns the endpoint URL and instance details as a structured result

When wired into Goose, an agent can say "provision a T4 with Gemma" and Goose will:
- Call `gpu_provision` via MCP
- Get back `endpoint_url` (OpenAI-compatible)
- Switch its provider to that endpoint via `openai_compatible.rs`
- Use it immediately for the rest of the session

### MCP Server Implementation Plan

**File to create:** `C:/Users/keith/dev/gpu-skill-builder/goose_skill_server.py`

Use the `mcp` Python SDK (`pip install mcp`). The server pattern is:

```python
from mcp.server.fastmcp import FastMCP
from skill import run_skill_sync

mcp = FastMCP("gpu-skill-builder")

@mcp.tool()
def gpu_provision(
    provider: str,
    hardware_slug: str,
    model_repo_id: str,
    instance_name: str,
    max_deployment_hours: int = 2,
    region: str = "us-east-1",
) -> dict:
    """Provision a GPU instance and return an OpenAI-compatible endpoint."""
    result = run_skill_sync(
        provider=provider,
        hardware_slug=hardware_slug,
        model_repo_id=model_repo_id,
        instance_name=instance_name,
        max_hours=max_deployment_hours,
        region=region,
        agent_mode=True,
    )
    if result.success and result.instance:
        return {
            "success": True,
            "endpoint_url": result.instance.endpoint_url,
            "instance_id": result.instance.id,
            "provider": result.instance.provider.value,
            "hardware": result.instance.hardware_slug,
            "model": result.instance.model_repo_id,
            "status": result.instance.status,
        }
    return {"success": False, "message": result.message}

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

### Steps

1. **Add `mcp` to requirements.txt** — `mcp>=1.0`
2. **Create `goose_skill_server.py`** using the pattern above
3. **Test the server standalone:**
   ```bash
   echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | python goose_skill_server.py
   ```
   Should return the `gpu_provision` tool schema.
4. **Write a Goose config snippet** in `BENCHMARKS.md` and in `.claude/skills/gpu-builder.md` showing how to wire it:
   ```yaml
   # ~/.config/goose/config.yaml
   extensions:
     gpu_provision:
       type: stdio
       cmd: python
       args: ["C:/Users/keith/dev/gpu-skill-builder/goose_skill_server.py"]
       envs: {}
   ```
5. **Write a Goose skill `.md` file** at `.claude/skills/goose-gpu-provision.md` (Goose-facing, not Claude-facing) describing the tool and when to use it
6. **Smoke test end-to-end** by running Goose CLI with the extension and asking it to provision something

### Validation Criteria

- `tools/list` returns `gpu_provision` with correct schema
- `tools/call` with valid params calls `run_skill_sync` and returns `endpoint_url`
- `tools/call` with invalid provider returns `success: false` with message (not a crash)
- Goose config loads the extension without error on `goose run`

---

## Priority 2: Goose as a 5th Benchmark Runner

### What to Build

Add `run_goose()` to `.bench/harness_benchmark.py` alongside the existing four runners, and wire it into `run_harness()`.

### How Goose CLI Works for Single-Turn Tasks

```bash
goose run --no-session -m openai/q --with-extension '...' "your prompt here"
```

Or using a recipe YAML for structured output. The key flags:
- `--no-session` — single-turn, no persistence
- `-m <provider>/<model>` — model selector
- `--with-extension` — inline extension JSON (or use config file)

Check the goose CLI help to confirm exact flags:
```bash
C:/Users/keith/dev/goose/target/release/goose run --help
```
(or wherever goose binary is after build — check `C:/Users/keith/dev/goose/`)

### Goose Binary Location

The repo is Rust — it needs to be built first if not already:
```bash
cd C:/Users/keith/dev/goose
cargo build --release
# binary at: target/release/goose (or goose.exe on Windows)
```
Check if a pre-built binary or npm package exists before building from source — look for `package.json` or releases.

### Implementation Plan

**In `.bench/harness_benchmark.py`:**

1. Add config constants:
```python
GOOSE_CLI = os.environ.get("BENCH_GOOSE_CLI", str(Path.home() / ".local/bin/goose"))
GOOSE_MODEL = os.environ.get("BENCH_GOOSE_MODEL", "openai/q")
```

2. Add `run_goose()` function following the same pattern as `run_claude()`:
```python
def run_goose(prompt: str, timeout_s: int = 300) -> Dict[str, Any]:
    env = os.environ.copy()
    env["OPENAI_API_KEY"] = "dummy"
    env["OPENAI_HOST"] = OPENAI_BASE_URL  # Goose uses OPENAI_HOST for base URL
    cmd = [
        GOOSE_CLI,
        "run",
        "--no-session",
        "-m", GOOSE_MODEL,
        prompt,
    ]
    with tempfile.TemporaryDirectory() as tmp:
        out = run_cmd(cmd, env, timeout_s, cwd=tmp)
    # Goose outputs markdown — extract code block
    response = strip_ansi(out["stdout"]).strip()
    out["response_text"] = response
    return out
```

3. Add to `run_harness()`:
```python
if harness == "goose":
    return run_goose(prompt)
```

4. Add `"goose"` to `HARNESS_ORDER` list.

5. Update `run_named_suite.py` — add `"goose"` to `choices` in argparse.

### Key Unknown: Goose CLI Invocation

Before implementing, verify:
- How Goose CLI accepts a single prompt (flag? positional arg? stdin?)
- What env var controls OpenAI base URL (`OPENAI_HOST`? `OPENAI_BASE_URL`? `GOOSE_OPENAI_HOST`?)
- Whether `--no-session` exists or if it's `--session false` or similar
- Output format (markdown? JSON? raw text?)

Check by running:
```bash
goose --help
goose run --help
```
And look at `/crates/goose-cli/src/main.rs` and `/crates/goose-cli/src/commands/run.rs` in the goose repo.

### Env Var for OpenAI Base URL

In goose, look for how `OPENAI_HOST` or `OPENAI_BASE_URL` is read. Search:
```bash
grep -r "OPENAI_HOST\|OPENAI_BASE_URL\|base_url" C:/Users/keith/dev/goose/crates/goose/src/providers/openai_compatible.rs
```

---

## What NOT to Do

- Do not modify the existing four runners (claude/codex/opencode/qwen) — they are validated and working
- Do not change `run_skill()` signature — `run_skill_sync()` is the sync wrapper for external callers
- Do not add MCP dependencies to the main `requirements.txt` without checking if `mcp` package conflicts with existing deps
- Do not build the goose binary unless no pre-built binary exists — it will take a long time
- Do not attempt Priority 3 (Open Model Gym backend integration) until Priorities 1 and 2 are done

---

## File Checklist

### New files to create:
- [ ] `goose_skill_server.py` — MCP stdio server
- [ ] `.claude/skills/goose-gpu-provision.md` — Goose-facing skill definition

### Files to modify:
- [ ] `requirements.txt` — add `mcp>=1.0`
- [ ] `.bench/harness_benchmark.py` — add `run_goose()`, constants, `HARNESS_ORDER` entry
- [ ] `.bench/run_named_suite.py` — add `"goose"` to argparse choices
- [ ] `.bench/BENCHMARKS.md` — document goose runner and Goose config snippet
- [ ] `.claude/skills/gpu-builder.md` — add Goose MCP wiring instructions
- [ ] `README.md` — add Goose integration section

### Commits (suggested grouping):
1. `feat(goose): MCP stdio server exposing gpu_provision tool` — `goose_skill_server.py` + `requirements.txt`
2. `feat(bench): add goose as 5th benchmark runner` — `.bench/` changes
3. `docs: document Goose integration and MCP wiring` — README, skill files, BENCHMARKS.md

---

## How to Start the CLI Session

```bash
cd C:/Users/keith/dev/gpu-skill-builder
claude --dangerously-skip-permissions
```

Opening prompt suggestion:
> "Check memory and read claude-vs-cli-handoff.md — we're implementing Goose integration with gpu-skill-builder. Start with Priority 1: the MCP stdio server."

---

## Repo State at Handoff

- Branch: `main`
- Clean working tree (all changes committed and pushed to GitHub)
- Last commit: `485e9ca` — docs: update provider status, harness validation, and DO runbook
- Ahead of origin: 0 (fully synced)
- Goose repo: cloned at `C:/Users/keith/dev/goose`, not modified
