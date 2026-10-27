#!/usr/bin/env python3
"""Generate deterministic synthetic M-Pesa SaaS analytics data.

Example (PowerShell):
  py -m pip install -r requirements.txt
  py generate_mock_data.py --sessions 10000 --seed 42 --as-of 2026-10-27 --out-dir data

All records are synthetic. Nothing is sent to GA4 or M-Pesa.
"""
from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from faker import Faker

TZ = "Africa/Nairobi"
NAMESPACE = uuid.UUID("a21e9e17-cba8-41cf-aa5d-9e97d9a51c75")

CHANNELS: list[dict[str, Any]] = [
    {"weight": .34, "source": "facebook", "medium": "paid_social", "campaigns": ["meta_sme_awareness", "meta_invoice_reconciliation", "meta_retargeting"], "campaign_weights": [.46, .34, .20], "checkout_rate": .065, "initiation_rate": .78, "success_rate": .64, "mobile_share": .82},
    {"weight": .14, "source": "google", "medium": "cpc", "campaigns": ["google_search_mpesa_reconciliation", "google_search_invoice_automation", "google_brand_search"], "campaign_weights": [.43, .37, .20], "checkout_rate": .175, "initiation_rate": .86, "success_rate": .79, "mobile_share": .57},
    {"weight": .18, "source": "google", "medium": "organic", "campaigns": ["seo_mpesa_reconciliation_guide", "seo_invoice_templates", "seo_cashflow_content"], "campaign_weights": [.45, .30, .25], "checkout_rate": .105, "initiation_rate": .81, "success_rate": .72, "mobile_share": .68},
    {"weight": .14, "source": None, "medium": None, "campaigns": [None], "campaign_weights": [1.0], "checkout_rate": .12, "initiation_rate": .82, "success_rate": .73, "mobile_share": .59},
    {"weight": .08, "source": "newsletter", "medium": "email", "campaigns": ["email_sme_tips", "email_feature_announcement", "email_reactivation"], "campaign_weights": [.42, .33, .25], "checkout_rate": .19, "initiation_rate": .88, "success_rate": .77, "mobile_share": .47},
    {"weight": .07, "source": "partner_referral", "medium": "referral", "campaigns": ["partner_accountants", "sme_community", "fintech_directory"], "campaign_weights": [.42, .35, .23], "checkout_rate": .12, "initiation_rate": .82, "success_rate": .70, "mobile_share": .58},
    {"weight": .05, "source": "linkedin", "medium": "paid_social", "campaigns": ["linkedin_sme_operations", "linkedin_finance_managers"], "campaign_weights": [.58, .42], "checkout_rate": .075, "initiation_rate": .77, "success_rate": .66, "mobile_share": .46},
]
FAILURES = [
    ("1", "Insufficient funds", .28),
    ("1032", "Request cancelled by user", .36),
    ("1037", "Payment request timed out or user did not respond", .23),
    ("2001", "Payment processing error", .13),
]
PAGES = ["/", "/pricing", "/mpesa-reconciliation", "/invoice-management", "/demo", "/blog/mpesa-reconciliation-guide"]
PAGE_WEIGHTS = [.20, .22, .20, .16, .10, .12]


def weighted_choice(rng: np.random.Generator, items: list[Any], weights: list[float]) -> Any:
    probs = np.asarray(weights, dtype=float)
    probs = probs / probs.sum()
    return items[int(rng.choice(len(items), p=probs))]


def parse_as_of(value: str | None) -> pd.Timestamp:
    if value:
        ts = pd.Timestamp(value)
        if ts.tzinfo is None:
            ts = ts.tz_localize(TZ)
        else:
            ts = ts.tz_convert(TZ)
        if len(value.strip()) == 10:
            ts = ts.normalize() + pd.Timedelta(hours=23, minutes=59, seconds=59)
        return ts
    return pd.Timestamp.now(tz=TZ).floor("s")


def choose_referrer(channel: dict[str, Any], rng: np.random.Generator) -> str | None:
    source, medium = channel["source"], channel["medium"]
    choices: list[str | None]
    if source == "facebook":
        choices = ["https://l.facebook.com/", "https://www.facebook.com/", None]
    elif source == "google" and medium == "cpc":
        choices = ["https://www.google.com/", "https://www.google.co.ke/"]
    elif source == "google":
        choices = ["https://www.google.com/", "https://www.google.co.ke/", "https://www.bing.com/"]
    elif source == "newsletter":
        choices = [None, "https://mail.google.com/"]
    elif source == "partner_referral":
        choices = ["https://smecommunity.example/", "https://accountants.example/", "https://directory.example/"]
    elif source == "linkedin":
        choices = ["https://www.linkedin.com/", "https://lnkd.in/"]
    else:
        choices = [None]
    return choices[int(rng.integers(0, len(choices)))]


def make_amount(rng: np.random.Generator) -> int:
    # Simulated KES invoice amounts: a right-skewed distribution with a long tail.
    draw = rng.random()
    if draw < .70:
        amount = rng.lognormal(np.log(1200), .70)
    elif draw < .94:
        amount = rng.lognormal(np.log(6500), .55)
    else:
        amount = rng.lognormal(np.log(25000), .45)
    return int(max(100, round(min(max(amount, 100), 100000) / 10) * 10))


def _ts(value: pd.Timestamp) -> str:
    return value.isoformat(timespec="seconds")


def generate_dataset(number_of_sessions: int, seed: int, as_of: pd.Timestamp):
    """Return (sessions, events, orders, summary), all reproducible for a fixed seed/as_of."""
    if number_of_sessions < 1000:
        raise ValueError("Use at least 1000 sessions; 10000 is recommended.")

    rng = np.random.default_rng(seed)
    fake = Faker("en_KE")
    fake.seed_instance(seed)
    # Use the first second of the starting calendar day so the entire six-month window is covered.
    start = as_of.normalize() - pd.DateOffset(months=6)

    days = pd.date_range(start=start.normalize(), end=as_of.normalize(), freq="D")
    day_idx = np.arange(len(days), dtype=float)
    growth = np.linspace(.72, 1.28, len(days))
    weekday_weights = np.array([1.02, 1.08, 1.10, 1.12, 1.06, .91, .70])
    weekly = weekday_weights[days.dayofweek]
    monthly = 1 + .16 * np.sin((2 * np.pi * day_idx / 29.5) + .7)
    day_probs = growth * weekly * monthly
    day_probs /= day_probs.sum()
    selected = rng.choice(len(days), size=number_of_sessions, p=day_probs)
    start_times: list[pd.Timestamp] = []
    for idx in selected:
        day = days[int(idx)]
        lo = max(0, int((start - day).total_seconds())) if day.date() == start.date() else 0
        hi = min(86399, int((as_of - day).total_seconds())) if day.date() == as_of.date() else 86399
        sec = int(rng.integers(lo, max(lo, hi) + 1))
        start_times.append(day + pd.Timedelta(seconds=sec))
    start_times.sort()

    sessions: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    orders: list[dict[str, Any]] = []
    next_order_id = 1
    client_ids: list[str] = []
    session_fields = ["session_id", "started_at", "utm_source", "utm_medium", "utm_campaign", "landing_page", "referrer", "device_category", "data_origin", "ga_client_id"]
    order_fields = ["id", "session_id", "phone_number", "amount", "status", "checkout_request_id", "merchant_request_id", "result_code", "result_desc", "mpesa_receipt_number", "created_at", "updated_at"]
    event_fields = ["event_id", "session_id", "event_name", "order_id", "occurred_at", "event_source", "properties"]

    for i, started in enumerate(start_times, start=1):
        channel = weighted_choice(rng, CHANNELS, [c["weight"] for c in CHANNELS])
        campaign = weighted_choice(rng, channel["campaigns"], channel["campaign_weights"])
        mobile_share = channel["mobile_share"]
        device = weighted_choice(rng, ["mobile", "desktop", "tablet"], [mobile_share, (1-mobile_share)*.82, (1-mobile_share)*.18])
        session_id = str(uuid.uuid5(NAMESPACE, f"session:{seed}:{i}"))
        if client_ids and rng.random() < .28:
            client_id = client_ids[int(rng.integers(0, len(client_ids)))]
        else:
            client_id = f"SIMCLIENT.{seed}.{len(client_ids)+1:08d}"
            client_ids.append(client_id)
        landing = weighted_choice(rng, PAGES, PAGE_WEIGHTS)
        sessions.append({
            "session_id": session_id, "started_at": _ts(started),
            "utm_source": channel["source"], "utm_medium": channel["medium"], "utm_campaign": campaign,
            "landing_page": landing, "referrer": choose_referrer(channel, rng), "device_category": device,
            "data_origin": "synthetic", "ga_client_id": client_id,
        })

        latest = min(started + pd.Timedelta(seconds=int(rng.integers(0, 4))), as_of)
        session_event_rows: list[dict[str, Any]] = [{
            "session_id": session_id, "event_name": "page_view", "order_id": None,
            "occurred_at": _ts(latest), "event_source": "web",
            "properties": {"page_location": landing, "page_type": landing.strip("/").split("/")[-1] or "home", "is_landing_page": True, "device_category": device},
        }]
        additional = weighted_choice(rng, [0, 1, 2, 3], [.55, .32, .10, .03])
        for _ in range(additional):
            latest = min(latest + pd.Timedelta(seconds=int(rng.integers(8, 76))), as_of)
            page = weighted_choice(rng, PAGES, PAGE_WEIGHTS)
            session_event_rows.append({
                "session_id": session_id, "event_name": "page_view", "order_id": None,
                "occurred_at": _ts(latest), "event_source": "web",
                "properties": {"page_location": page, "page_type": page.strip("/").split("/")[-1] or "home", "is_landing_page": False, "device_category": device},
            })
        events.extend(session_event_rows)

        checkout_prob = channel["checkout_rate"] * (1.02 if device == "mobile" else .93 if device == "tablet" else 1.0)
        if rng.random() >= checkout_prob:
            continue

        checkout_time = min(latest + pd.Timedelta(seconds=int(rng.integers(4, 46))), as_of)
        checkout_idx = len(events)
        events.append({
            "session_id": session_id, "event_name": "begin_checkout", "order_id": None,
            "occurred_at": _ts(checkout_time), "event_source": "web",
            "properties": {"checkout_method": "mpesa_stk_push", "currency": "KES", "device_category": device},
        })
        if rng.random() < .035:
            error = weighted_choice(rng, ["client_validation", "network_error", "checkout_service_unavailable"], [.32, .48, .20])
            error_time = min(checkout_time + pd.Timedelta(seconds=int(rng.integers(1, 8))), as_of)
            events.append({
                "session_id": session_id, "event_name": "checkout_error", "order_id": None,
                "occurred_at": _ts(error_time), "event_source": "api",
                "properties": {"error_type": error, "stage": "before_order_creation", "currency": "KES"},
            })
            continue
        if rng.random() >= channel["initiation_rate"]:
            continue

        oid = next_order_id
        next_order_id += 1
        events[checkout_idx]["order_id"] = oid
        initiated = min(checkout_time + pd.Timedelta(seconds=int(rng.integers(2, 12))), as_of)
        events.append({
            "session_id": session_id, "event_name": "payment_initiated", "order_id": oid,
            "occurred_at": _ts(initiated), "event_source": "api",
            "properties": {"payment_method": "mpesa_stk_push", "currency": "KES", "source_system": "synthetic_checkout_api"},
        })

        if rng.random() < .045:
            status, result_code, result_desc, receipt = "PENDING", None, None, None
            updated = min(initiated + pd.Timedelta(minutes=int(rng.integers(5, 46))), as_of)
        elif rng.random() < channel["success_rate"] - (.015 if device == "mobile" else 0):
            status, result_code = "SUCCESS", "0"
            result_desc, receipt = "The service request is processed successfully", f"SYN{oid:09d}"
            updated = min(initiated + pd.Timedelta(seconds=int(rng.integers(4, 121))), as_of)
            events.append({
                "session_id": session_id, "event_name": "payment_succeeded", "order_id": oid,
                "occurred_at": _ts(updated), "event_source": "mpesa_callback",
                "properties": {"payment_method": "mpesa_stk_push", "currency": "KES", "result_code": "0", "synthetic_receipt": True},
            })
        else:
            result_code, result_desc = weighted_choice(rng, [(x[0], x[1]) for x in FAILURES], [x[2] for x in FAILURES])
            status, receipt = "FAILED", None
            updated = min(initiated + pd.Timedelta(seconds=int(rng.integers(4, 121))), as_of)
            events.append({
                "session_id": session_id, "event_name": "payment_failed", "order_id": oid,
                "occurred_at": _ts(updated), "event_source": "mpesa_callback",
                "properties": {"payment_method": "mpesa_stk_push", "currency": "KES", "result_code": result_code, "failure_reason": result_desc},
            })

        orders.append({
            "id": oid, "session_id": session_id,
            # Clearly synthetic marker rather than a real-looking/routable phone number.
            "phone_number": fake.bothify(text="SYNTHETIC-KE-########"),
            "amount": make_amount(rng), "status": status,
            "checkout_request_id": f"SIM-CO-{oid:08d}", "merchant_request_id": f"SIM-MR-{oid:08d}",
            "result_code": result_code, "result_desc": result_desc, "mpesa_receipt_number": receipt,
            "created_at": _ts(initiated), "updated_at": _ts(updated),
        })

    sdf = pd.DataFrame(sessions, columns=session_fields)
    odf = pd.DataFrame(orders, columns=order_fields)
    edf = pd.DataFrame(events)
    if edf.empty:
        edf = pd.DataFrame(columns=["session_id", "event_name", "order_id", "occurred_at", "event_source", "properties"])
    edf = edf.sort_values(["occurred_at", "session_id", "event_name"], kind="stable").reset_index(drop=True)
    edf.insert(0, "event_id", np.arange(1, len(edf) + 1, dtype=np.int64))
    edf["order_id"] = pd.array(edf["order_id"], dtype="Int64")
    edf["properties"] = edf["properties"].map(lambda x: json.dumps(x or {}, sort_keys=True, separators=(",", ":")))

    validate_dataset(sdf, edf, odf, as_of)
    successful = odf[odf["status"] == "SUCCESS"]
    summary = {
        "start": start.isoformat(), "end": as_of.isoformat(), "n_sessions": len(sdf), "n_events": len(edf), "n_orders": len(odf),
        "event_counts": edf["event_name"].value_counts().to_dict(),
        "order_status_counts": odf["status"].value_counts().to_dict(),
        "sessions_with_checkout": int(edf.loc[edf.event_name == "begin_checkout", "session_id"].nunique()),
        "payment_attempts": int(edf.loc[edf.event_name == "payment_initiated", "order_id"].nunique()),
        "successful_orders": len(successful), "successful_revenue_kes": int(successful["amount"].sum()) if len(successful) else 0,
        "successful_aov_kes": round(float(successful["amount"].mean()), 2) if len(successful) else 0.0,
        "channel_sessions": (sdf.assign(channel=sdf.utm_source.fillna("direct") + "/" + sdf.utm_medium.fillna("(none)"))["channel"].value_counts().to_dict()),
        "failure_reasons": odf.loc[odf.status == "FAILED", "result_desc"].value_counts().to_dict(),
    }
    return sdf, edf, odf, summary


def validate_dataset(sessions: pd.DataFrame, events: pd.DataFrame, orders: pd.DataFrame, as_of: pd.Timestamp) -> None:
    """Fail fast when essential referential, status, time, ID, or privacy checks fail."""
    assert len(sessions) >= 1000
    assert sessions.session_id.is_unique
    assert sessions.data_origin.eq("synthetic").all()
    assert sessions.started_at.notna().all()
    assert events.event_id.is_unique if "event_id" in events.columns else True
    session_ids = set(sessions.session_id)
    order_ids = set(orders.id.astype(int))
    assert events.session_id.isin(session_ids).all()
    non_null_event_orders = events.loc[events.order_id.notna(), "order_id"].astype(int)
    assert non_null_event_orders.isin(order_ids).all()
    assert orders.id.is_unique
    assert orders.session_id.isin(session_ids).all()
    if not orders.empty:
        assert (pd.to_numeric(orders.amount) > 0).all()
        assert orders.status.isin(["SUCCESS", "FAILED", "PENDING"]).all()
        created = pd.to_datetime(orders.created_at, utc=True)
        updated = pd.to_datetime(orders.updated_at, utc=True)
        assert (updated >= created).all()
        succ = orders[orders.status == "SUCCESS"]
        fail = orders[orders.status == "FAILED"]
        pending = orders[orders.status == "PENDING"]
        assert succ.result_code.eq("0").all() and succ.mpesa_receipt_number.notna().all()
        assert fail.result_code.notna().all() and fail.mpesa_receipt_number.isna().all()
        assert pending.result_code.isna().all() and pending.mpesa_receipt_number.isna().all()
    initiated = set(events.loc[events.event_name == "payment_initiated", "order_id"].dropna().astype(int))
    assert initiated == order_ids
    event_success = set(events.loc[events.event_name == "payment_succeeded", "order_id"].dropna().astype(int))
    event_failed = set(events.loc[events.event_name == "payment_failed", "order_id"].dropna().astype(int))
    status_success = set(orders.loc[orders.status == "SUCCESS", "id"].astype(int))
    status_failed = set(orders.loc[orders.status == "FAILED", "id"].astype(int))
    assert event_success == status_success
    assert event_failed == status_failed
    props = events.properties.astype(str)
    assert not props.str.contains(r"\+2547\d{8}", regex=True).any()
    assert not props.str.contains("phone_number", case=False).any()
    event_times = pd.to_datetime(events.occurred_at, utc=True)
    assert event_times.max() <= as_of.tz_convert("UTC") if len(event_times) else True


def write_summary(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "PROJECT 2 SYNTHETIC DATASET SUMMARY", "===================================",
        f"Window: {summary['start']} through {summary['end']}",
        f"Sessions: {summary['n_sessions']:,}", f"Events: {summary['n_events']:,}", f"Orders: {summary['n_orders']:,}",
        f"Sessions with checkout: {summary['sessions_with_checkout']:,}", f"Payment attempts: {summary['payment_attempts']:,}",
        f"Successful orders: {summary['successful_orders']:,}", f"Verified revenue (KES): {summary['successful_revenue_kes']:,}",
        f"Successful-order AOV (KES): {summary['successful_aov_kes']:,.2f}", "", "Channel sessions:",
    ]
    lines.extend(f"  {k}: {v:,}" for k, v in summary["channel_sessions"].items())
    lines.extend(["", "Event counts:"])
    lines.extend(f"  {k}: {v:,}" for k, v in summary["event_counts"].items())
    lines.extend(["", "Order statuses:"])
    lines.extend(f"  {k}: {v:,}" for k, v in summary["order_status_counts"].items())
    lines.extend(["", "Failure reasons:"])
    lines.extend(f"  {k}: {v:,}" for k, v in summary["failure_reasons"].items())
    lines.extend(["", "All data is synthetic. Phone_number values are non-routable identifiers; no real payment or analytics service is contacted."])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Project 2 synthetic revenue analytics data.")
    parser.add_argument("--sessions", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--as-of", default=None, help="Date or datetime in Nairobi time; set this to reproduce the same time window.")
    parser.add_argument("--out-dir", type=Path, default=Path("data"))
    args = parser.parse_args()
    if args.sessions < 1000:
        parser.error("--sessions must be at least 1000")
    as_of = parse_as_of(args.as_of)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Generating {args.sessions:,} sessions (seed={args.seed}, as_of={as_of.isoformat()}) ...")
    sessions, events, orders, summary = generate_dataset(args.sessions, args.seed, as_of)
    sessions.to_csv(args.out_dir / "analytics_sessions.csv", index=False)
    orders.to_csv(args.out_dir / "orders.csv", index=False)
    events.to_csv(args.out_dir / "analytics_events.csv", index=False)
    write_summary(args.out_dir / "dataset_summary.txt", summary)
    print("SUCCESS: generated and validated all datasets")
    for name, count in [("analytics_sessions.csv", len(sessions)), ("orders.csv", len(orders)), ("analytics_events.csv", len(events))]:
        print(f"  {name}: {count:,} rows")
    print(f"Verified revenue (KES): {summary['successful_revenue_kes']:,}")
    print(f"Output: {args.out_dir.resolve()}")

if __name__ == "__main__":
    main()
