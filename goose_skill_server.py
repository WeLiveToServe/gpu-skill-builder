"""
MCP stdio server — exposes gpu_provision as a tool for Goose agents.

Usage (standalone test):
    echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | python goose_skill_server.py

Goose config snippet (~/.config/goose/config.yaml):
    extensions:
      gpu_provision:
        type: stdio
        cmd: python
        args: ["C:/Users/keith/dev/gpu-skill-builder/goose_skill_server.py"]
        envs: {}

When wired in, Goose agents can call gpu_provision to provision a GPU instance
and immediately use the returned endpoint_url as an OpenAI-compatible backend.
"""

import sys
import os

# Ensure the project root is on the path so skill.py can be imported
sys.path.insert(0, os.path.dirname(__file__))

from mcp.server.fastmcp import FastMCP
from skill import run_skill_sync

mcp = FastMCP("gpu-skill-builder")


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
    mcp.run(transport="stdio")
