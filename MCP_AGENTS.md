# gpu-skill-builder MCP Agent Config Reference

`goose_skill_server.py` is an MCP stdio server exposing the `gpu_provision` tool.
Any MCP-compatible agent can call it — this doc is the copy-paste config for each
supported ecosystem.

**What the tool does:** Provisions a GPU instance (HuggingFace, Modal, or DigitalOcean),
loads a model, and returns an OpenAI-compatible `endpoint_url` the agent can use immediately.

---

## Transport modes

The server supports three transport modes:

| Mode | Command | Use case |
|------|---------|----------|
| `stdio` (default) | `python goose_skill_server.py` | Local agents (Goose, Claude Code, OpenCode, Cursor) |
| `sse` | `python goose_skill_server.py --transport sse --port 3333` | Remote agents, browser-based tools |
| `streamable-http` | `python goose_skill_server.py --transport streamable-http --port 3333` | Stateless HTTP, firewall-friendly |

All local agents use stdio — no server process needed, they spawn it as a subprocess.

---

## 1. Goose

**Config file:** `%APPDATA%\Block\goose\config\config.yaml` (Windows) or `~/.config/goose/config.yaml`

**Status: wired and verified** ✓

```yaml
extensions:
  gpu_skill_builder:
    enabled: true
    type: stdio
    name: gpu_skill_builder
    display_name: GPU Skill Builder
    description: Provision GPU instances and get OpenAI-compatible endpoints via gpu-skill-builder
    cmd: python
    args:
      - C:/Users/keith/dev/gpu-skill-builder/goose_skill_server.py
    envs: {}
    bundled: false
    timeout: 300
```

**Verify:**
```bash
GOOSE_PROVIDER=openai GOOSE_MODEL="google/gemma-4-31B-it" OPENAI_API_KEY=dummy \
  OPENAI_HOST=http://127.0.0.1:18000 \
  goose run --no-session --text "List the tool names available to you." --quiet
# Should include: gpu_skill_builder__gpu_provision
```

---

## 2. Claude Code

**Config file:** `.mcp.json` at project root (committed). Approved via `.claude/settings.local.json`.

**Status: wired** ✓ (active on next session start)

`.mcp.json`:
```json
{
  "mcpServers": {
    "gpu-skill-builder": {
      "command": "python",
      "args": ["C:/Users/keith/dev/gpu-skill-builder/goose_skill_server.py"]
    }
  }
}
```

`.claude/settings.local.json` — add alongside `permissions`:
```json
{
  "enableAllProjectMcpServers": true,
  "permissions": { ... }
}
```

**Verify:** Start a new Claude Code session in this project. The `gpu-skill-builder` MCP server
will appear in `/mcp` status. Claude can then call `gpu_provision` directly as a tool.

**Note:** Path in `.mcp.json` is machine-specific. Update to match your local clone path if
working on another machine.

---

## 3. OpenCode

**Config file:** `~/.config/opencode/opencode.json`

**Status: wired** ✓

Add to your existing `opencode.json` under the `"mcp"` key:

```json
{
  "mcp": {
    "gpu-skill-builder": {
      "type": "local",
      "command": ["python", "C:/Users/keith/dev/gpu-skill-builder/goose_skill_server.py"],
      "enabled": true,
      "timeout": 300000
    }
  }
}
```

**Verify:**
```bash
opencode mcp list
# Should show: gpu-skill-builder
```

---

## 4. Cursor

**Config file:** `.cursor/mcp.json` in your project root (Cursor picks it up automatically).

```json
{
  "mcpServers": {
    "gpu-skill-builder": {
      "command": "python",
      "args": ["C:/Users/keith/dev/gpu-skill-builder/goose_skill_server.py"]
    }
  }
}
```

After adding, open Cursor Settings → MCP → verify `gpu-skill-builder` shows as connected.

---

## 5. Any agent — HTTP/SSE mode

For agents that don't support stdio MCP, or for remote access, run the server in HTTP mode:

```bash
# Start HTTP/SSE server (keep running in background)
python C:/Users/keith/dev/gpu-skill-builder/goose_skill_server.py --transport sse --port 3333

# Or stateless HTTP:
python C:/Users/keith/dev/gpu-skill-builder/goose_skill_server.py --transport streamable-http --port 3333 --host 0.0.0.0
```

Connect from any MCP client that supports SSE:
- SSE endpoint: `http://127.0.0.1:3333/sse`
- StreamableHTTP endpoint: `http://127.0.0.1:3333/mcp`

**Remote access example (Goose connecting to SSE):**
```yaml
extensions:
  gpu_skill_builder_remote:
    type: sse
    uri: http://YOUR_SERVER_IP:3333/sse
```

---

## Tool schema

```
gpu_provision(
  provider: str,               # "huggingface" | "modal" | "digitalocean"
  hardware_slug: str,          # e.g. "nvidia-t4-x1", "h100", "gpu-h200x1-141gb"
  model_repo_id: str,          # HuggingFace repo ID, e.g. "google/gemma-4-31B-it"
  instance_name: str = "gpu-skill-instance",
  max_deployment_hours: int = 2,
  region: str = "us-east-1"
) -> {
  success: bool,
  endpoint_url: str,           # OpenAI-compatible base URL
  instance_id: str,
  provider: str,
  hardware: str,
  model: str,
  status: str
}
```

## Prerequisites

- Python with `mcp>=1.0` installed (`pip install mcp`)
- `~/dev/.env` with provider credentials (`HF_TOKEN`, `MODAL_TOKEN_ID`/`MODAL_TOKEN_SECRET`, `DO_TOKEN`)
- The server resolves credentials via pydantic-settings — no hardcoded keys anywhere
