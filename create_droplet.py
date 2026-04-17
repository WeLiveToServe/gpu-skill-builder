"""
create_droplet.py — CLI entry point for spinning up a DO GPU droplet.

Usage:
    python create_droplet.py
    python create_droplet.py --size gpu-h200x1-141gb
    python create_droplet.py --size gpu-h100x1-80gb --name my-droplet
    python create_droplet.py --destroy <droplet-id>

Replaces create-h100-droplet.ps1 and create-h200-droplet.ps1.
"""

import argparse
import asyncio
import sys

import httpx

from do_bootstrap import create_droplet, resolve_token, _headers, DO_API


async def destroy_droplet(droplet_id: int) -> None:
    token = resolve_token()
    resp = httpx.delete(
        f"{DO_API}/droplets/{droplet_id}",
        headers=_headers(token),
        timeout=15,
    )
    if resp.status_code == 204:
        print(f"Droplet {droplet_id} destroyed.")
    elif resp.status_code == 404:
        print(f"Droplet {droplet_id} not found (already gone).")
    else:
        print(f"Unexpected response {resp.status_code}: {resp.text}")
        sys.exit(1)


async def list_droplets() -> None:
    token = resolve_token()
    resp = httpx.get(f"{DO_API}/droplets?per_page=200", headers=_headers(token), timeout=15)
    resp.raise_for_status()
    droplets = resp.json().get("droplets", [])
    if not droplets:
        print("No droplets.")
        return
    for d in droplets:
        nets = d.get("networks", {}).get("v4", [])
        ip = next((n["ip_address"] for n in nets if n["type"] == "public"), "no-ip")
        print(f"  id={d['id']}  name={d['name']}  size={d['size_slug']}  "
              f"status={d['status']}  ip={ip}  region={d['region']['slug']}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Manage DO GPU droplets")
    parser.add_argument("--size", default="gpu-h100x1-80gb",
                        help="Droplet size slug (default: gpu-h100x1-80gb)")
    parser.add_argument("--name", default="agent-harness-h100",
                        help="Droplet name (default: agent-harness-h100)")
    parser.add_argument("--destroy", type=int, metavar="DROPLET_ID",
                        help="Destroy a droplet by ID")
    parser.add_argument("--list", action="store_true",
                        help="List all current droplets")
    args = parser.parse_args()

    if args.list:
        await list_droplets()
        return

    if args.destroy:
        await destroy_droplet(args.destroy)
        return

    info = await create_droplet(size=args.size, name=args.name)

    print()
    print("=" * 50)
    print(f"  Droplet ready")
    print("=" * 50)
    print(f"  ID:      {info.id}")
    print(f"  Name:    {info.name}")
    print(f"  IP:      {info.ip}")
    print(f"  Region:  {info.region}")
    print(f"  Size:    {info.size}")
    print(f"  SSH:     {info.ssh_command}")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
