"""
MCP server — exposes gpu_provision as a tool for any MCP-compatible agent.

Transport modes:
    stdio (default):
        python goose_skill_server.py
        python goose_skill_server.py --transport stdio

    HTTP/SSE (for remote agents or browser-based tools):
        python goose_skill_server.py --transport sse --port 3333
        python goose_skill_server.py --transport streamable-http --port 3333 --host 0.0.0.0

Standalone stdio test:
    python - <<'EOF'
    import subprocess, json
    proc = subprocess.Popen(["python","goose_skill_server.py"], stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    proc.stdin.write(json.dumps({"jsonrpc":"2.0","id":1,"method":"initialize","params":{
        "protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"t","version":"0"}
    }}) + "\\n")
    proc.stdin.write(json.dumps({"jsonrpc":"2.0","method":"notifications/initialized","params":{}}) + "\\n")
    proc.stdin.flush()
    proc.stdout.readline()  # init response
    proc.stdin.write(json.dumps({"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}) + "\\n")
    proc.stdin.flush()
    print(proc.stdout.readline())
    proc.terminate()
    EOF
"""

import argparse
import sys
import os

# Ensure the project root is on the path so skill.py can be imported
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.fastmcp import FastMCP
from skill import run_skill_sync

def _parse_args():
    parser = argparse.ArgumentParser(description="gpu-skill-builder MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="Transport mode (default: stdio)",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host for HTTP transports (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=3333, help="Port for HTTP transports (default: 3333)")
    # Only parse args when run as __main__; when imported by an MCP host (e.g. Claude Code)
    # the host passes no args, so we fall back safely to defaults.
    return parser.parse_args()

mcp = FastMCP("gpu-skill-builder", host="127.0.0.1", port=3333)


@mcp.tool()
def gpu_provision(
    provider: str,
    hardware_slug: str,
    model_repo_id: str,
    instance_name: str = "gpu-skill-instance",
    max_deployment_hours: int = 2,
    region: str = "us-east-1",
) -> dict:
    """
    Provision a GPU instance and load an open-source model onto it.

    Returns an OpenAI-compatible endpoint_url that can be used immediately
    as a backend (e.g. via Goose's openai_compatible provider).

    Args:
        provider: One of 'huggingface', 'modal', 'digitalocean'.
        hardware_slug: Provider-specific hardware identifier
            (e.g. 'nvidia-t4-x1' for HuggingFace, 'h100' for Modal).
        model_repo_id: HuggingFace repo ID of the model to load
            (e.g. 'google/gemma-2-2b-it').
        instance_name: Logical name for the instance (used for idempotency).
        max_deployment_hours: Auto-destroy TTL in hours (default 2).
        region: Cloud region hint (provider-specific, default 'us-east-1').

    Returns:
        On success: {success: true, endpoint_url, instance_id, provider,
                     hardware, model, status}
        On failure: {success: false, message}
    """
    result = run_skill_sync(
        provider=provider,
        hardware_slug=hardware_slug,
        model_repo_id=model_repo_id,
        instance_name=instance_name,
        max_deployment_hours=max_deployment_hours,
        region=region,
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
    args = _parse_args()
    if args.transport != "stdio":
        # Rebuild mcp with the requested host/port before running HTTP transport
        mcp.settings.host = args.host
        mcp.settings.port = args.port
    mcp.run(transport=args.transport)
