#!/usr/bin/env python3
"""
DigitalOcean billing query helper for GPU skill-builder workflows.

Current focus:
- Query account balance.
- Query billing history.
- Query invoices and optional invoice summaries.
- Persist timestamped snapshots and detect changes between runs.

Future focus:
- This script is intended to become a provider-specific backend in a
  multi-provider billing abstraction.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


API_BASE = "https://api.digitalocean.com/v2"
DEFAULT_PER_PAGE = 200


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Query DigitalOcean billing data and store local snapshots."
    )
    parser.add_argument(
        "--token",
        default=None,
        help="DigitalOcean API token (falls back to env vars if omitted).",
    )
    parser.add_argument(
        "--env-file",
        default=None,
        help="Optional .env file to load before reading token variables.",
    )
    parser.add_argument(
        "--out-dir",
        default="billing-query-providers/output",
        help="Directory for snapshot and state files.",
    )
    parser.add_argument(
        "--state-file",
        default=None,
        help="Optional custom path for state file.",
    )
    parser.add_argument(
        "--per-page",
        type=int,
        default=DEFAULT_PER_PAGE,
        help="Pagination page size for list endpoints.",
    )
    parser.add_argument(
        "--invoice-summary-limit",
        type=int,
        default=5,
        help="Number of newest invoices to enrich with summary endpoint calls.",
    )
    return parser.parse_args()


def load_dotenv(path: pathlib.Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


def resolve_token(explicit: str | None) -> str:
    if explicit:
        return explicit
    for key in ("DIGITALOCEAN_ACCESS_TOKEN", "DIGITALOCEAN_TOKEN"):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    raise RuntimeError(
        "Missing DigitalOcean token. Provide --token or set "
        "DIGITALOCEAN_ACCESS_TOKEN / DIGITALOCEAN_TOKEN."
    )


def do_get(token: str, path: str, query: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{API_BASE}{path}"
    if query:
        url = f"{url}?{urllib.parse.urlencode(query)}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        body = err.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {err.code} for {url}: {body}") from err
    except urllib.error.URLError as err:
        raise RuntimeError(f"Network error while requesting {url}: {err}") from err


def fetch_paginated(token: str, path: str, list_key: str, per_page: int) -> list[dict[str, Any]]:
    page = 1
    items: list[dict[str, Any]] = []
    while True:
        payload = do_get(token, path, {"per_page": per_page, "page": page})
        chunk = payload.get(list_key, [])
        if not isinstance(chunk, list):
            break
        items.extend(chunk)
        if len(chunk) < per_page:
            break
        page += 1
    return items


def summarize_credit_signals(
    billing_history: list[dict[str, Any]],
    invoice_summaries: list[dict[str, Any]],
) -> dict[str, Any]:
    credit_events: list[dict[str, Any]] = []
    for item in billing_history:
        text_fields = [
            str(item.get("type", "")),
            str(item.get("description", "")),
            str(item.get("amount", "")),
        ]
        joined = " ".join(text_fields).lower()
        if any(word in joined for word in ("credit", "promo", "adjustment", "coupon")):
            credit_events.append(item)

    invoices_with_credit_adjustments: list[dict[str, Any]] = []
    for invoice_summary in invoice_summaries:
        summary = invoice_summary.get("summary", {})
        credits = summary.get("credits_and_adjustments")
        if isinstance(credits, dict):
            amount = credits.get("amount")
            invoices_with_credit_adjustments.append(
                {
                    "invoice_uuid": invoice_summary.get("invoice_uuid"),
                    "invoice_id": summary.get("invoice_id"),
                    "billing_period": summary.get("billing_period"),
                    "credits_and_adjustments_amount": amount,
                }
            )

    return {
        "credit_like_billing_events": credit_events,
        "invoice_credit_adjustment_signals": invoices_with_credit_adjustments,
    }


def stable_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def load_json(path: pathlib.Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    args = parse_args()
    repo_root = pathlib.Path.cwd()

    if args.env_file:
        load_dotenv(pathlib.Path(args.env_file))
    else:
        local_env = repo_root / ".env"
        if local_env.exists():
            load_dotenv(local_env)

    try:
        token = resolve_token(args.token)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    try:
        balance = do_get(token, "/customers/my/balance")
        billing_history = fetch_paginated(
            token, "/customers/my/billing_history", "billing_history", args.per_page
        )
        invoices_response = do_get(token, "/customers/my/invoices", {"per_page": args.per_page, "page": 1})
        invoices = invoices_response.get("invoices", [])
        invoice_preview = invoices_response.get("invoice_preview")

        invoice_summaries: list[dict[str, Any]] = []
        limit = max(0, args.invoice_summary_limit)
        for invoice in invoices[:limit]:
            invoice_uuid = invoice.get("invoice_uuid")
            if not invoice_uuid:
                continue
            summary = do_get(token, f"/customers/my/invoices/{invoice_uuid}/summary")
            invoice_summaries.append({"invoice_uuid": invoice_uuid, "summary": summary})
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    credit_signals = summarize_credit_signals(billing_history, invoice_summaries)
    now_utc = dt.datetime.now(dt.timezone.utc)
    stamp = now_utc.strftime("%Y%m%dT%H%M%SZ")

    report = {
        "provider": "digitalocean",
        "fetched_at_utc": now_utc.isoformat(),
        "balance": balance,
        "counts": {
            "billing_history_entries": len(billing_history),
            "invoices_returned": len(invoices),
            "invoice_summaries_fetched": len(invoice_summaries),
        },
        "invoice_preview": invoice_preview,
        "billing_history": billing_history,
        "invoices": invoices,
        "invoice_summaries": invoice_summaries,
        "credit_signals": credit_signals,
    }

    out_dir = pathlib.Path(args.out_dir)
    state_path = pathlib.Path(args.state_file) if args.state_file else out_dir / "digitalocean_billing_state.json"
    snapshot_path = out_dir / f"digitalocean_billing_snapshot_{stamp}.json"
    latest_path = out_dir / "digitalocean_billing_latest.json"

    state_payload = {
        "balance": report.get("balance"),
        "invoice_preview": report.get("invoice_preview"),
        "credit_signals": report.get("credit_signals"),
        "counts": report.get("counts"),
    }
    state_hash = stable_hash(state_payload)
    previous_state = load_json(state_path) or {}
    previous_hash = previous_state.get("state_hash")
    changed = state_hash != previous_hash

    write_json(snapshot_path, report)
    write_json(latest_path, report)
    write_json(
        state_path,
        {
            "provider": "digitalocean",
            "updated_at_utc": now_utc.isoformat(),
            "state_hash": state_hash,
            "changed_since_last_run": changed,
        },
    )

    print("DigitalOcean billing query complete.")
    print(f"Snapshot: {snapshot_path}")
    print(f"Latest:   {latest_path}")
    print(f"State:    {state_path}")
    print(f"Changed:  {'yes' if changed else 'no'}")
    print(
        "Balance:  month_to_date_usage={usage} month_to_date_balance={mtd} account_balance={acc}".format(
            usage=balance.get("month_to_date_usage", "n/a"),
            mtd=balance.get("month_to_date_balance", "n/a"),
            acc=balance.get("account_balance", "n/a"),
        )
    )
    print(
        "Signals:  billing_history_entries={hist} credit_like_events={credits} invoices={invoices}".format(
            hist=len(billing_history),
            credits=len(credit_signals.get("credit_like_billing_events", [])),
            invoices=len(invoices),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
