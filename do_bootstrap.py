"""
do_bootstrap.py — Hardened DigitalOcean droplet provisioning.

Single entry point for all DO droplet creation in this project. Handles:
  - Token resolution (doctl → .env → fail loudly)
  - SSH key validation and self-healing (regenerates if missing/corrupt)
  - Live region discovery (never hardcoded)
  - Idempotent droplet creation (returns existing if found)
  - Poll-until-active with proper timeout and error handling

Usage:
    from do_bootstrap import create_droplet
    info = await create_droplet(size="gpu-h100x1-80gb")
    print(info.ssh_command)
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

DO_API = "https://api.digitalocean.com/v2"
ENV_FILE = Path.home() / "dev" / ".env"
SSH_KEY_PATH = Path.home() / ".ssh" / "do_agent_ed25519"
STATE_FILE = Path(__file__).parent / ".do_state.json"
PROJECT_ID = "8513a898-7103-4d2f-a503-ffb24008e609"
GPU_IMAGE = "gpu-h100x1-base"
DEFAULT_TAGS = ["gpu", "agent-harness", "llm"]
POLL_INTERVAL = 10   # seconds between status checks
POLL_TIMEOUT = 300   # seconds before giving up


# ── Return type ───────────────────────────────────────────────────────────────

@dataclass
class DropletInfo:
    id: int
    name: str
    ip: str
    region: str
    size: str
    status: str
    ssh_key_path: str = str(SSH_KEY_PATH)

    @property
    def ssh_command(self) -> str:
        return f"ssh -i {self.ssh_key_path} root@{self.ip}"


# ── State file (stores DO key ID so we don't search by name every call) ───────

def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_state(state: dict) -> None:
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(STATE_FILE)


# ── Token resolution ──────────────────────────────────────────────────────────

def resolve_token() -> str:
    """
    Returns a valid DO API token. Priority:
      1. doctl auth token (most reliable — survives .env corruption)
      2. DIGITALOCEAN_ACCESS_TOKEN in .env
    Writes back to .env if the stored value is stale.
    Raises RuntimeError with a clear message if neither source works.
    """
    token = _token_from_doctl()
    if token:
        _sync_token_to_env(token)
        return token

    token = _token_from_env()
    if token:
        return token

    raise RuntimeError(
        "No DigitalOcean token found.\n"
        "Run: doctl auth init\n"
        f"Or set DIGITALOCEAN_ACCESS_TOKEN in {ENV_FILE}"
    )


def _token_from_doctl() -> str | None:
    try:
        result = subprocess.run(
            ["doctl", "auth", "token"],
            capture_output=True, text=True, timeout=10
        )
        token = result.stdout.strip()
        if token.startswith("dop_v1_"):
            return token
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def _token_from_env() -> str | None:
    if not ENV_FILE.exists():
        return None
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("DIGITALOCEAN_ACCESS_TOKEN="):
            value = line.split("=", 1)[1].strip()
            if value.startswith("dop_v1_"):
                return value
    return None


def _sync_token_to_env(token: str) -> None:
    """Keep .env in sync with whatever doctl has."""
    if not ENV_FILE.exists():
        return
    text = ENV_FILE.read_text(encoding="utf-8")
    new_line = f"DIGITALOCEAN_ACCESS_TOKEN={token}"
    # Replace existing line or append
    if re.search(r"^DIGITALOCEAN_ACCESS_TOKEN=", text, re.MULTILINE):
        text = re.sub(r"^DIGITALOCEAN_ACCESS_TOKEN=.*$", new_line, text, flags=re.MULTILINE)
    else:
        text = text.rstrip("\n") + f"\n{new_line}\n"
    ENV_FILE.write_text(text, encoding="utf-8")


# ── SSH key management ────────────────────────────────────────────────────────

def ensure_ssh_key(token: str) -> int:
    """
    Ensures ~/.ssh/do_agent_ed25519 exists and is valid.
    If missing or corrupt: regenerates the keypair, removes the old DO key,
    registers the new public key, and returns the new DO key ID.
    Returns the DO key ID (from state, from DO lookup, or freshly registered).
    """
    state = _load_state()

    if _key_is_valid():
        # Key looks good — verify it's registered in DO
        key_id = state.get("do_ssh_key_id")
        if key_id and _do_key_exists(token, key_id):
            return key_id
        # Not in state or was deleted — look it up by name first
        key_id = _find_do_key_by_name(token, "do-agent-harness")
        if key_id:
            state["do_ssh_key_id"] = key_id
            _save_state(state)
            return key_id
        # Not registered at all — register it now
        return _register_key(token, state)

    # Key is missing or corrupt — full regeneration
    logger.warning("SSH key at %s is missing or corrupt. Regenerating...", SSH_KEY_PATH)
    _regenerate_keypair()

    # Remove stale DO key if we have its ID or can find it by name.
    # Clear key ID from state before deletion so that if _register_key() fails,
    # state does not point at a deleted key on the next call.
    old_id = state.get("do_ssh_key_id") or _find_do_key_by_name(token, "do-agent-harness")
    if old_id:
        state.pop("do_ssh_key_id", None)
        _save_state(state)
        _delete_do_key(token, old_id)

    return _register_key(token, state)


def _key_is_valid() -> bool:
    if not SSH_KEY_PATH.exists():
        return False
    content = SSH_KEY_PATH.read_text(errors="replace")
    return content.strip().startswith("-----BEGIN OPENSSH PRIVATE KEY-----")


def _regenerate_keypair() -> None:
    SSH_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Write a temp placeholder so ssh-keygen -f doesn't ask interactively
    if SSH_KEY_PATH.exists():
        SSH_KEY_PATH.unlink()
    pub = Path(str(SSH_KEY_PATH) + ".pub")
    if pub.exists():
        pub.unlink()

    subprocess.run(
        ["ssh-keygen", "-t", "ed25519", "-f", str(SSH_KEY_PATH),
         "-N", "", "-C", "agent@do-agent-harness"],
        check=True, capture_output=True
    )
    logger.info("New keypair written to %s", SSH_KEY_PATH)


def _find_do_key_by_name(token: str, name: str) -> int | None:
    resp = httpx.get(f"{DO_API}/account/keys?per_page=200",
                     headers=_headers(token), timeout=10)
    if resp.status_code != 200:
        return None
    for key in resp.json().get("ssh_keys", []):
        if key["name"] == name:
            return key["id"]
    return None


def _do_key_exists(token: str, key_id: int) -> bool:
    resp = httpx.get(f"{DO_API}/account/keys/{key_id}",
                     headers=_headers(token), timeout=10)
    return resp.status_code == 200


def _delete_do_key(token: str, key_id: int) -> None:
    httpx.delete(f"{DO_API}/account/keys/{key_id}",
                 headers=_headers(token), timeout=10)


def _register_key(token: str, state: dict) -> int:
    pub_path = Path(str(SSH_KEY_PATH) + ".pub")
    public_key = pub_path.read_text().strip()
    resp = httpx.post(
        f"{DO_API}/account/keys",
        headers=_headers(token),
        json={"name": "do-agent-harness", "public_key": public_key},
        timeout=10,
    )
    resp.raise_for_status()
    key_id = resp.json()["ssh_key"]["id"]
    state["do_ssh_key_id"] = key_id
    _save_state(state)
    logger.info("SSH key registered in DigitalOcean (ID: %d)", key_id)
    return key_id


# ── Region discovery ──────────────────────────────────────────────────────────

def find_available_region(token: str, size_slug: str) -> str:
    """
    Queries /v2/sizes live and returns the first available region for size_slug.
    Never hardcodes a region — they rotate constantly.
    Raises ValueError if no region is available.
    """
    resp = httpx.get(f"{DO_API}/sizes?per_page=200",
                     headers=_headers(token), timeout=15)
    resp.raise_for_status()

    for size in resp.json().get("sizes", []):
        if size["slug"] == size_slug and size.get("available") and size.get("regions"):
            region = size["regions"][0]
            logger.info("Region for %s: %s", size_slug, region)
            return region

    raise ValueError(
        f"Size '{size_slug}' has no available regions right now. "
        "Check https://cloud.digitalocean.com/droplets/new for availability."
    )


# ── Idempotency check ─────────────────────────────────────────────────────────

def find_existing_droplet(token: str, name: str) -> DropletInfo | None:
    """Returns a running droplet with this name, or None."""
    resp = httpx.get(f"{DO_API}/droplets?per_page=200",
                     headers=_headers(token), timeout=15)
    resp.raise_for_status()

    for d in resp.json().get("droplets", []):
        if d["name"] == name and d["status"] in ("new", "active"):
            ip = _extract_ip(d)
            if ip:
                logger.info("Found existing droplet '%s' (ID=%s, IP=%s). Reusing.", name, d["id"], ip)
                return _to_info(d, ip)
    return None


# ── Core create + poll ────────────────────────────────────────────────────────

async def create_droplet(
    size: str = "gpu-h100x1-80gb",
    name: str = "agent-harness-h100",
    project_id: str = PROJECT_ID,
    image: str = GPU_IMAGE,
    extra_tags: list[str] | None = None,
) -> DropletInfo:
    """
    Idempotent. Creates a DO droplet and polls until active.
    Returns a DropletInfo with IP, SSH command, etc.
    Handles token resolution, SSH key validation, and region discovery automatically.
    """
    token = resolve_token()
    key_id = ensure_ssh_key(token)

    # Idempotency: don't create if one already exists
    existing = find_existing_droplet(token, name)
    if existing:
        return existing

    region = find_available_region(token, size)
    tags = list(set(DEFAULT_TAGS + (extra_tags or []) + [size.split("-")[1]]))

    logger.info("Creating droplet '%s' (%s in %s)...", name, size, region)
    resp = httpx.post(
        f"{DO_API}/droplets",
        headers=_headers(token),
        json={
            "name": name,
            "region": region,
            "size": size,
            "image": image,
            "ssh_keys": [str(key_id)],
            "project_id": project_id,
            "tags": tags,
        },
        timeout=30,
    )

    if resp.status_code not in (201, 202):
        raise RuntimeError(
            f"Droplet creation failed ({resp.status_code}): {resp.text}"
        )

    droplet_id = resp.json()["droplet"]["id"]
    logger.info("Droplet created (ID=%s). Polling for active state...", droplet_id)

    info = await _poll_until_active(token, droplet_id, name)

    # Persist IP to file for other tools
    ip_file = Path(__file__).parent / f"{name}-ip.txt"
    ip_file.write_text(info.ip)

    state = _load_state()
    state["last_droplet"] = {"id": info.id, "name": info.name, "ip": info.ip, "region": info.region}
    _save_state(state)

    return info


async def _poll_until_active(token: str, droplet_id: int, name: str) -> DropletInfo:
    elapsed = 0
    async with httpx.AsyncClient(headers=_headers(token), timeout=15) as client:
        while elapsed < POLL_TIMEOUT:
            await asyncio.sleep(POLL_INTERVAL)
            elapsed += POLL_INTERVAL

            resp = await client.get(f"{DO_API}/droplets/{droplet_id}")

            if resp.status_code == 404:
                raise RuntimeError(
                    f"Droplet {droplet_id} not found during polling — "
                    "it may have been deleted or failed to provision."
                )

            if resp.status_code != 200:
                logger.debug("  [%ds] poll returned %s, retrying...", elapsed, resp.status_code)
                continue

            d = resp.json()["droplet"]
            status = d["status"]
            ip = _extract_ip(d)
            logger.info("  [%3ds] status=%s  ip=%s", elapsed, status, ip or "pending")

            if status == "active" and ip:
                logger.info("Droplet '%s' is active at %s", name, ip)
                return _to_info(d, ip)

            if status == "errored":
                raise RuntimeError(
                    f"Droplet {droplet_id} entered errored state. "
                    "Check the DigitalOcean control panel for details."
                )

    raise TimeoutError(
        f"Droplet {droplet_id} did not become active within {POLL_TIMEOUT}s."
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _extract_ip(droplet: dict) -> str | None:
    for net in droplet.get("networks", {}).get("v4", []):
        if net["type"] == "public":
            return net["ip_address"]
    return None


def _to_info(d: dict, ip: str) -> DropletInfo:
    return DropletInfo(
        id=d["id"],
        name=d["name"],
        ip=ip,
        region=d["region"]["slug"],
        size=d["size_slug"],
        status=d["status"],
    )
