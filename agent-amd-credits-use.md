# Agent Notes: AMD Developer Cloud Credits and GPU Droplet Provisioning

## Purpose

This document is for an agent that needs to understand the current state of AMD Developer Cloud / DigitalOcean GPU access on this machine and on this account.

The key question investigated was:

> Why does the account appear to have AMD GPU credits, but MI300X droplet creation fails through the public API?

## Executive Summary

The PAT works.

The account can create:

- regular CPU droplets
- at least one public GPU droplet type (`gpu-h200x1-141gb` in `atl1`)

The account cannot create:

- `gpu-mi300x1-192gb`
- `gpu-l40sx1-48gb`

The failure is **not** authentication and **not** generic droplet permission.

The failure is that AMD GPU sizes are **not present in the account's effective per-region inventory**, even though they appear in the global size catalog.

That is why `POST /v2/droplets` returns:

`422 Size is not available in this region`

## Important Account Context

### Team

- Team name: `My AMD Team`
- Team UUID: `23b1010c-b39d-4f77-ba81-5d80661fc260`

### Projects

- Default project: `My AMD Home`
- Project for LLM work: `llm-inference-api-tests`
- Project ID: `8513a898-7103-4d2f-a503-ffb24008e609`

### Token

A DigitalOcean PAT was stored locally in:

- [`.env`](C:/Users/keith/dev/.env)

The following names were used:

- `DIGITALOCEAN_ACCESS_TOKEN`
- `DIGITALOCEAN_TOKEN`

### SSH Key

The existing local SSH key pair used for registration:

- public key: [oci_ampere_ed25519.pub](C:/Users/keith/.ssh/oci_ampere_ed25519.pub)
- private key: [oci_ampere_ed25519](C:/Users/keith/.ssh/oci_ampere_ed25519)

Registered DigitalOcean SSH key:

- name: `codex-do-oci-ampere`
- ID: `55531916`

## What Was Actually Done

### 1. Install and use `doctl`

`doctl` was installed globally with `winget`.

In the current session, the `PATH` was extended manually to ensure the binary resolved immediately:

```powershell
$env:PATH += ';C:\Users\keith\AppData\Local\Microsoft\WinGet\Packages\DigitalOcean.Doctl_Microsoft.Winget.Source_8wekyb3d8bbwe'
```

### 2. Load the PAT from the local env file

The token was read from [`.env`](C:/Users/keith/dev/.env) and exported into the session:

```powershell
$env:DIGITALOCEAN_ACCESS_TOKEN = (Get-Content C:\Users\keith\dev\.env |
  Select-String '^DIGITALOCEAN_ACCESS_TOKEN=' |
  ForEach-Object { $_.ToString().Split('=',2)[1] })
```

### 3. Validate token/account access

Used:

```powershell
doctl account get
```

Result:

- success
- account active
- email verified
- team shown as `My AMD Team`

### 4. Register the SSH public key

Used:

```powershell
doctl compute ssh-key import codex-do-oci-ampere --public-key-file "$HOME\.ssh\oci_ampere_ed25519.pub"
```

Result:

- success
- SSH key ID `55531916`

### 5. Verify ordinary droplet creation works

A tiny CPU droplet was created as a scope test:

```powershell
doctl compute droplet create codex-scope-test `
  --region nyc1 `
  --size s-1vcpu-512mb-10gb `
  --image ubuntu-24-04-x64 `
  --project-id 8513a898-7103-4d2f-a503-ffb24008e609 `
  --ssh-keys 55531916 `
  --tag-names scope-test `
  --wait `
  --format ID,Name,PublicIPv4,Region,Status `
  --no-header
```

Result:

- success
- droplet created and became active

That proves:

- token works
- project works
- droplet create scope works

### 6. Attempt to create AMD MI300X and L40S droplets

Tried:

- `gpu-mi300x1-192gb`
- `gpu-l40sx1-48gb`

Across likely public regions including:

- `nyc1`
- `nyc2`
- `nyc3`
- `sfo2`
- `sfo3`
- `ams3`
- `fra1`
- `tor1`
- `atl1`
- `lon1`
- `sgp1`
- `syd1`
- `blr1`

Typical create command shape:

```powershell
doctl compute droplet create amd-qwen35-mi300x `
  --region atl1 `
  --size gpu-mi300x1-192gb `
  --image gpu-amd-base `
  --project-id 8513a898-7103-4d2f-a503-ffb24008e609 `
  --ssh-keys 55531916 `
  --tag-names amd,qwen,mi300x,llm `
  --wait
```

Result every time:

```text
Error: POST https://api.digitalocean.com/v2/droplets: 422 ... Size is not available in this region.
```

### 7. Query the real region inventory

This was the most important diagnostic step.

The global size list is **not enough**. The real source of truth is `/v2/regions`, which includes a `sizes` array per region.

Used Python stdlib HTTP:

```python
import json, os, urllib.request

req = urllib.request.Request(
    'https://api.digitalocean.com/v2/regions?per_page=200',
    headers={'Authorization': 'Bearer ' + os.environ['DOTOKEN']}
)
with urllib.request.urlopen(req) as r:
    data = json.load(r)

for region in data.get('regions', []):
    gpu = [s for s in region.get('sizes', []) if s.startswith('gpu-')]
    if gpu:
        print(region['slug'], gpu)
```

Result for this account:

- `atl1 ['gpu-h200x1-141gb']`

No region exposed:

- `gpu-mi300x1-192gb`
- `gpu-l40sx1-48gb`

### 8. Verify at least one GPU droplet can be created

Created an H200 probe droplet:

```powershell
doctl compute droplet create codex-h200-probe `
  --region atl1 `
  --size gpu-h200x1-141gb `
  --image gpu-h100x1-base `
  --project-id 8513a898-7103-4d2f-a503-ffb24008e609 `
  --ssh-keys 55531916 `
  --tag-names gpu,probe,h200 `
  --format ID,Name,PublicIPv4,Region,Image,Status `
  --no-header
```

Result:

- success
- droplet was accepted and entered `new` state

It was then deleted immediately to avoid burning credits.

That proves:

- GPU droplets are possible on this token/account
- the blocker is specific to AMD GPU availability, not generic GPU prohibition

## Interpretive Conclusion

The account is in a partially enabled state:

- normal droplet provisioning works
- some GPU provisioning works
- AMD GPU provisioning does not work

The most likely explanation is:

**AMD GPU entitlement for this team/account is not fully enabled on the backend, even though AMD GPU credits are present in the UI and AMD GPU sizes appear in the global catalog.**

## What The Credits Are Likely For

Based on AMD's own docs:

- credits appear intended for **AMD Instinct MI300X**
- credits are not for ordinary CPU droplets
- credits likely do not cover storage / backup extras
- credits may continue burning on powered-off GPU VMs

So `MI300X` is the correct target conceptually.

## Why OAuth Is Not The Current Answer

OAuth app registration is not the relevant path for this workflow.

The PAT already proved it can:

- read account/project state
- import SSH keys
- create droplets
- create at least one GPU droplet

So the problem is not “need OAuth instead of PAT.”

## Recommended Agent Behavior

If an agent is asked to launch AMD MI300X on this account:

1. load PAT from [`.env`](C:/Users/keith/dev/.env)
2. export it as `DIGITALOCEAN_ACCESS_TOKEN`
3. ensure `doctl` is on `PATH`
4. query `/v2/regions`
5. check whether `gpu-mi300x1-192gb` appears in any region's `sizes`
6. if not present, do **not** blindly loop create attempts forever
7. report that AMD GPU entitlement appears missing or not fully provisioned

If an agent only needs to verify GPU provisioning in principle:

1. check whether `gpu-h200x1-141gb` appears in `atl1`
2. if yes, optionally create a temporary H200 probe droplet
3. delete it immediately after confirmation

## Practical Next Step

The next real fix is likely support-side.

A support request should include:

- team name: `My AMD Team`
- project ID: `8513a898-7103-4d2f-a503-ffb24008e609`
- AMD GPU promo credits exist in the UI
- PAT can create CPU droplets
- PAT can create `gpu-h200x1-141gb` in `atl1`
- PAT cannot create `gpu-mi300x1-192gb`
- `/v2/regions` for this account does not expose MI300X in any region
- `POST /v2/droplets` returns `422 Size is not available in this region`

## Important Files

- local env: [`.env`](C:/Users/keith/dev/.env)
- SSH public key: [oci_ampere_ed25519.pub](C:/Users/keith/.ssh/oci_ampere_ed25519.pub)
- SSH private key: [oci_ampere_ed25519](C:/Users/keith/.ssh/oci_ampere_ed25519)
- human-readable summary: [human-amd-credits-use.md](C:/Users/keith/Desktop/claw-management-resources/human-amd-credits-use.md)

## Bottom Line

The correct automation lesson is:

**Do not trust the global size list. Trust the account-scoped region inventory.**

On this account, the region inventory currently exposes H200 but not MI300X. Until that changes, AMD credits exist in theory but are not actually usable for MI300X droplet creation through the public API path.
