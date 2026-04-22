# Billing Query Notes

This repo now includes a provider-specific billing query starter under:

- `billing-query-providers/digitalocean_billing_query.py`

## Current objective (DigitalOcean only)

The script is intentionally DigitalOcean-specific right now and is meant to help us:

- Query current account balance via API.
- Pull billing history entries.
- Pull invoices and optional invoice summaries.
- Store timestamped snapshots for diffing over time.
- Detect whether billing/credit-related state changed since the previous run.

This gives the repo a practical baseline for tracking DigitalOcean spend and credit behavior from local scripts.

## Usage

Run from repo root:

```bash
python billing-query-providers/digitalocean_billing_query.py
```

Optional flags:

- `--env-file <path>`: Load token vars from a specific env file.
- `--token <token>`: Override token directly.
- `--out-dir <path>`: Change output directory (default `billing-query-providers/output`).
- `--invoice-summary-limit <n>`: Number of newest invoices to enrich with summaries.

Token lookup order:

1. `--token` (if provided)
2. `DIGITALOCEAN_ACCESS_TOKEN`
3. `DIGITALOCEAN_TOKEN`

If `--env-file` is not passed, the script attempts to load `./.env` from the current working directory.

## Output files

The script writes:

- `digitalocean_billing_snapshot_<timestamp>.json`
- `digitalocean_billing_latest.json`
- `digitalocean_billing_state.json`

in the output directory.

`digitalocean_billing_state.json` contains a stable hash of key billing fields so we can quickly detect changes between runs.

## Current scope

This README is about the current DigitalOcean billing query helper only.

Multi-provider billing normalization is **not** implemented as part of the main skill runtime today.
