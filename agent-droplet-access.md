# Agent Droplet Access

## Purpose

This file gives an agent the exact information needed to access the current DigitalOcean GPU droplet and understand its present state.

## Current Droplet

- name: `codex-h100-test`
- id: `564344866`
- provider: DigitalOcean
- region: `ams3`
- public IP: `188.166.100.8`
- status: `active`
- image: `Ubuntu NVIDIA AI/ML Ready Image`

## Hardware

- GPU: `NVIDIA H100 80GB HBM3`
- VRAM: about `81559 MiB`
- NVIDIA driver: `590.48.01`
- Docker: installed and working

## SSH Access

Use the local SSH key pair already on `local t480`:

- private key: [oci_ampere_ed25519](C:/Users/keith/.ssh/oci_ampere_ed25519)
- public key: [oci_ampere_ed25519.pub](C:/Users/keith/.ssh/oci_ampere_ed25519.pub)

SSH command:

```powershell
ssh -i "$HOME\.ssh\oci_ampere_ed25519" root@188.166.100.8
```

The root login was already verified successfully.

## API / Inference State

Current status:

- SSH works
- GPU is visible with `nvidia-smi`
- Docker works
- there is **no** inference API listening on port `8000` yet

This was verified from `local t480`:

```powershell
Test-NetConnection 188.166.100.8 -Port 8000
```

Result:

- `TcpTestSucceeded : False`

So the droplet is a live GPU box, but not yet a usable model API server.

## Local Credentials / Config

DigitalOcean token is stored locally in:

- [`.env`](C:/Users/keith/dev/.env)

Relevant vars:

- `DIGITALOCEAN_ACCESS_TOKEN`
- `DIGITALOCEAN_TOKEN`
- `HF_TOKEN`
- `HUGGINGFACE_TOKEN`

## Local CLI Access

`doctl` is installed globally via `winget`.

In PowerShell, if `doctl` is not on `PATH` yet in the current session, prepend:

```powershell
$env:PATH += ';C:\Users\keith\AppData\Local\Microsoft\WinGet\Packages\DigitalOcean.Doctl_Microsoft.Winget.Source_8wekyb3d8bbwe'
```

Then load the token from the local env:

```powershell
$env:DIGITALOCEAN_ACCESS_TOKEN = (Get-Content C:\Users\keith\dev\.env |
  Select-String '^DIGITALOCEAN_ACCESS_TOKEN=' |
  ForEach-Object { $_.ToString().Split('=',2)[1] })
```

Example droplet status check:

```powershell
doctl compute droplet list --format ID,Name,PublicIPv4,Region,Image,Status --no-header
```

## Minimal On-Box Checks

Once connected, the fastest sanity checks are:

```bash
hostname
nvidia-smi
docker --version
docker ps
ss -ltnp | grep 8000 || true
```

## What An Agent Should Assume

- This droplet is intended to become an inference box that other machines call via API.
- It is suitable for a large open model, but the serving stack is not yet running.
- Do **not** assume a model is already downloaded.
- Do **not** assume port `8000` is open or serving.

## Recommended Immediate Next Step

If the task is to make the droplet usable for inference:

1. SSH in as `root`
2. inspect Docker/NVIDIA runtime
3. choose the target model deliberately
4. launch a persistent server
5. verify remote reachability on the chosen API port

## Related Files

- human AMD credit summary: [human-amd-credits-use.md](C:/Users/keith/Desktop/claw-management-resources/human-amd-credits-use.md)
- agent AMD credit summary: [agent-amd-credits-use.md](C:/Users/keith/Desktop/agent-ec2-access/agent-amd-credits-use.md)
