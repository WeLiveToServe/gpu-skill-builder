# AMD Developer Cloud Credits: What They Actually Unlock

## Short Version

The problem is not your token.

Your `dop_v1_...` token is valid, has real droplet permissions, and can create both:

- normal CPU droplets
- at least one public GPU droplet type

What is failing is **AMD GPU availability for your account/team**, not authentication.

Right now, your account can see AMD GPU sizes like `gpu-mi300x1-192gb` in the global size catalog, but the real region inventory exposed to your token does **not** include them. That is why the API keeps returning:

`422: Size is not available in this region`

## What I Verified Live

I tested this directly against your account on **April 10, 2026**.

### Token and account

- `doctl account get` works
- your PAT is valid
- the account/team is real
- your SSH key can be imported successfully

### CPU droplets

I successfully created a tiny CPU droplet. That proves:

- the token has droplet creation permission
- the project is valid
- the account is not generally blocked from provisioning

### GPU droplets

I also successfully created an `H200` GPU droplet in `atl1`, then deleted it immediately to avoid wasting credits.

That proves:

- GPU droplet creation works in principle on this account
- the public API path is real
- the token is not missing generic GPU permissions

### AMD GPU attempts

I tried to create:

- `gpu-mi300x1-192gb`
- `gpu-l40sx1-48gb`

Those failed across all likely public regions with the same error:

`422: Size is not available in this region`

## The Key Technical Finding

The most useful endpoint here was not the global size list. It was the region inventory.

When I queried the raw `/v2/regions` response for your token/account, the GPU sizes actually available to your account were:

- `atl1`: `gpu-h200x1-141gb`

That was it.

No region exposed:

- `gpu-mi300x1-192gb`
- `gpu-l40sx1-48gb`

So the account can **see** more GPU sizes globally, but can only **actually create** the ones attached to its effective regional inventory.

That neatly explains why:

- `size list` looks promising
- MI300X create fails
- H200 create succeeds

## What The Official Docs Suggest

### AMD docs

AMD’s Developer Cloud materials say the complimentary credits are for **AMD Instinct MI300X GPU** usage via a third-party cloud platform.

AMD also says:

- credits are short-lived unless stated otherwise in the email
- volumes, object storage, and backups are not covered
- powered-off GPU VMs may still consume credits

So your memory that the credits are for **GPU droplets only** is consistent with the official AMD description.

### DigitalOcean docs

DigitalOcean’s docs currently say:

- MI300X is an AMD GPU droplet offering
- AMD GPUs may require support enablement
- GPU availability is region-dependent

One especially important line from the GPU docs is essentially:

**To use AMD GPUs, contact support to request access.**

That fits the behavior we are seeing.

## Most Likely Root Cause

The cleanest explanation is:

**Your account has working DigitalOcean droplet permissions, and even general GPU access, but AMD GPU entitlement has not actually been enabled on the backend for your team.**

That could mean one of a few closely related things:

- AMD MI300X access was not fully provisioned on your team
- the credits were granted before the backend entitlement was attached
- the AMD portal and the public API are not perfectly in sync yet
- there is a support-side enablement step still missing

But the practical result is the same:

**the credits exist, but MI300X is not yet launchable through your account’s real API-visible region inventory**

## What This Means For Credit Use

Based on the credits you shared:

- `$100` expires **April 29, 2026**
- `$100` expires **May 18, 2026**

So if MI300X access gets fixed, the right burn order is obvious:

1. use the **April 29, 2026** bucket first
2. then use the **May 18, 2026** bucket
3. preserve any 2028 credit if that exists outside this summary

## What This Does Not Mean

This does **not** mean:

- the PAT is wrong
- OAuth is required instead
- GPU droplets are impossible on your account
- MI300X is the wrong kind of resource

In fact, MI300X is the most likely **correct** target for these credits.

## Best Next Step

The most useful next action is to contact AMD Developer Cloud / DigitalOcean support with the contradiction stated plainly:

- the team has AMD GPU promo credits
- the token can create CPU droplets
- the token can create an H200 GPU droplet
- `gpu-mi300x1-192gb` is visible in the size catalog
- but `/v2/regions` never exposes MI300X for the account
- and every MI300X create attempt returns `422 Size is not available in this region`

That gives support a concrete backend problem to inspect instead of a vague “my credits don’t work.”

## Sources I Used

- AMD Developer Cloud page
- AMD Developer Cloud FAQ / terms
- DigitalOcean GPU droplet docs
- DigitalOcean availability docs
- live DigitalOcean API behavior on your token
- recent community discussion where available

## Limits Of This Investigation

- The Gmail PDFs you shared earlier were image-only `Print to PDF` exports, so I could confirm subjects/metadata but not extract full body text without OCR.
- Community discussion on this exact AMD credit program is still sparse.
- X/Twitter and some forum content were not reliably readable through the browser tooling.

## Bottom Line

You are not crazy.

The current evidence says your AMD credits are real, MI300X is the right target, and the actual blocker is that **AMD GPU droplet access is not fully enabled on the backend for your team/account yet**, even though other parts of the platform are working.
