#!/usr/bin/env python3
"""
Project 2: Synthetic Revenue & Product Intelligence Dataset Generator

Generates:
    analytics_sessions.csv
    analytics_events.csv
    orders.csv
    00_create_source_tables.sql
    dataset_summary.txt

Dependencies:
    py -m pip install pandas numpy Faker

Example:
    py project2_generate_dataset.py --sessions 10000 --seed 42 --out-dir project2_data

All generated records are synthetic.
The script does not connect to PostgreSQL, GA4, or M-Pesa.
"""

import argparse
import json
import random
import uuid
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
from faker import Faker


# ============================================================
# 1. CONFIGURATION
# ============================================================

TIMEZONE = "Africa/Nairobi"

CHANNELS = [
    {
        "weight": 0.34,
        "source": "facebook",
        "medium": "paid_social",
        "campaigns": [
            "meta_sme_awareness",
            "meta_invoice_reconciliation",
            "meta_retargeting",
        ],
        "campaign_weights": [0.46, 0.34, 0.20],
        "checkout_rate": 0.065,
        "initiation_rate": 0.78,
        "success_rate": 0.64,
        "mobile_share": 0.82,
    },
    {
        "weight": 0.14,
        "source": "google",
        "medium": "cpc",
        "campaigns": [
            "google_search_mpesa_reconciliation",
            "google_search_invoice_automation",
            "google_brand_search",
        ],
        "campaign_weights": [0.43, 0.37, 0.20],
        "checkout_rate": 0.175,
        "initiation_rate": 0.86,
        "success_rate": 0.79,
        "mobile_share": 0.57,
    },
    {
        "weight": 0.18,
        "source": "google",
        "medium": "organic",
        "campaigns": [
            "seo_mpesa_reconciliation_guide",
            "seo_invoice_templates",
            "seo_cashflow_content",
        ],
        "campaign_weights": [0.45, 0.30, 0.25],
        "checkout_rate": 0.105,
        "initiation_rate": 0.81,
        "success_rate": 0.72,
        "mobile_share": 0.68,
    },
    {
        "weight": 0.14,
        "source": None,
        "medium": None,
        "campaigns": [None],
        "campaign_weights": [1.0],
        "checkout_rate": 0.12,
        "initiation_rate": 0.82,
        "success_rate": 0.73,
        "mobile_share": 0.59,
    },
    {
        "weight": 0.08,
        "source": "newsletter",
        "medium": "email",
        "campaigns": [
            "email_sme_tips",
            "email_feature_announcement",
            "email_reactivation",
        ],
        "campaign_weights": [0.42, 0.33, 0.25],
        "checkout_rate": 0.19,
        "initiation_rate": 0.88,
        "success_rate": 0.77,
        "mobile_share": 0.47,
    },
    {
        "weight": 0.07,
        "source": "partner_referral",
        "medium": "referral",
        "campaigns": [
            "partner_accountants",
            "sme_community",
            "fintech_directory",
        ],
        "campaign_weights": [0.42, 0.35, 0.23],
        "checkout_rate": 0.12,
        "initiation_rate": 0.82,
        "success_rate": 0.70,
        "mobile_share": 0.58,
    },
    {
        "weight": 0.05,
        "source": "linkedin",
        "medium": "paid_social",
        "campaigns": [
            "linkedin_sme_operations",
            "linkedin_finance_managers",
        ],
        "campaign_weights": [0.58, 0.42],
        "checkout_rate": 0.075,
        "initiation_rate": 0.77,
        "success_rate": 0.66,
        "mobile_share": 0.46,
    },
]

FAILURE_OUTCOMES = [
    ("1", "Insufficient funds", 0.28),
    ("1032", "Request cancelled by user", 0.36),
    ("1037", "Payment request timed out or user did not respond", 0.23),
    ("2001", "Payment processing error", 0.13),
]

DEVICE_CATEGORIES = ["mobile", "desktop", "tablet"]


# ============================================================
# 2. POSTGRESQL SOURCE TABLE DEFINITIONS
# ============================================================

SCHEMA_SQL = r"""
CREATE SCHEMA IF NOT EXISTS project2;

CREATE TABLE IF NOT EXISTS project2.analytics_sessions (
    session_id UUID PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL,
    utm_source TEXT,
    utm_medium TEXT,
    utm_campaign TEXT,
    landing_page TEXT NOT NULL,
    referrer TEXT,
    device_category TEXT NOT NULL
        CHECK (device_category IN ('mobile', 'desktop', 'tablet')),
    data_origin TEXT NOT NULL DEFAULT 'synthetic'
        CHECK (data_origin = 'synthetic'),
    ga_client_id TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS project2.orders (
    id BIGINT PRIMARY KEY,
    session_id UUID NOT NULL
        REFERENCES project2.analytics_sessions(session_id),
    phone_number TEXT NOT NULL,
    amount NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
    status TEXT NOT NULL
        CHECK (status IN ('PENDING', 'SUCCESS', 'FAILED')),
    checkout_request_id TEXT NOT NULL UNIQUE,
    merchant_request_id TEXT NOT NULL UNIQUE,
    result_code TEXT,
    result_desc TEXT,
    mpesa_receipt_number TEXT UNIQUE,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CHECK (updated_at >= created_at),
    CHECK (
        (status = 'SUCCESS'
            AND result_code = '0'
            AND mpesa_receipt_number IS NOT NULL)
        OR
        (status = 'FAILED'
            AND result_code IS NOT NULL
            AND mpesa_receipt_number IS NULL)
        OR
        (status = 'PENDING'
            AND result_code IS NULL
            AND mpesa_receipt_number IS NULL)
    )
);

CREATE TABLE IF NOT EXISTS project2.analytics_events (
    event_id BIGINT PRIMARY KEY,
    session_id UUID NOT NULL
        REFERENCES project2.analytics_sessions(session_id),
    event_name TEXT NOT NULL
        CHECK (
            event_name IN (
                'page_view',
                'begin_checkout',
                'payment_initiated',
                'payment_succeeded',
                'payment_failed',
                'checkout_error'
            )
        ),
    order_id BIGINT
        REFERENCES project2.orders(id),
    occurred_at TIMESTAMPTZ NOT NULL,
    event_source TEXT NOT NULL
        CHECK (event_source IN ('web', 'api', 'mpesa_callback')),
    properties JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_project2_events_session_time
    ON project2.analytics_events(session_id, occurred_at);

CREATE INDEX IF NOT EXISTS idx_project2_events_name_time
    ON project2.analytics_events(event_name, occurred_at);

CREATE INDEX IF NOT EXISTS idx_project2_orders_status_created
    ON project2.orders(status, created_at);

CREATE INDEX IF NOT EXISTS idx_project2_sessions_started
    ON project2.analytics_sessions(started_at);
"""


# ============================================================
# 3. HELPER FUNCTIONS
# ============================================================

def weighted_choice(rng, items, weights):
    """Choose one item using the supplied probability weights."""
    probabilities = np.asarray(weights, dtype=float)
    probabilities = probabilities / probabilities.sum()

    index = rng.choice(len(items), p=probabilities)
    return items[int(index)]


def parse_as_of(value):
    """Parse the ending date and make it timezone-aware."""
    if value:
        timestamp = pd.Timestamp(value)

        if timestamp.tzinfo is None:
            timestamp = timestamp.tz_localize(TIMEZONE)
        else:
            timestamp = timestamp.tz_convert(TIMEZONE)

        if len(value.strip()) == 10:
            timestamp = (
                timestamp.normalize()
                + pd.Timedelta(hours=23, minutes=59, seconds=59)
            )

        return timestamp

    return pd.Timestamp.now(tz=TIMEZONE)


def generate_session_times(n, start, end, rng):
    """
    Generate session timestamps over six months.

    The simulation includes:
    - Gradual traffic growth
    - Different weekday and weekend traffic
    - A repeating monthly traffic pattern
    """
    days = pd.date_range(
        start=start.normalize(),
        end=end.normalize(),
        freq="D",
    )

    day_indices = np.arange(len(days), dtype=float)

    growth = np.linspace(0.72, 1.28, len(days))

    weekday_weights = np.array([
        1.02,  # Monday
        1.08,  # Tuesday
        1.10,  # Wednesday
        1.12,  # Thursday
        1.06,  # Friday
        0.91,  # Saturday
        0.70,  # Sunday
    ])

    weekly_pattern = weekday_weights[days.dayofweek]

    monthly_pattern = 1.0 + 0.16 * np.sin(
        (2 * np.pi * day_indices / 29.5) + 0.7
    )

    probabilities = growth * weekly_pattern * monthly_pattern
    probabilities = probabilities / probabilities.sum()

    selected_days = rng.choice(
        len(days),
        size=n,
        replace=True,
        p=probabilities,
    )

    timestamps = []

    for selected_index in selected_days:
        day = days[int(selected_index)]

        lower_seconds = 0
        upper_seconds = 86399

        if day.date() == start.date():
            lower_seconds = max(
                0,
                int((start - day).total_seconds()),
            )

        if day.date() == end.date():
            upper_seconds = min(
                86399,
                int((end - day).total_seconds()),
            )

        if upper_seconds < lower_seconds:
            seconds = lower_seconds
        else:
            seconds = int(
                rng.integers(lower_seconds, upper_seconds + 1)
            )

        timestamps.append(
            day + pd.Timedelta(seconds=seconds)
        )

    timestamps.sort()
    return timestamps


def get_referrer(channel, rng):
    """Generate a plausible referrer for an acquisition channel."""
    options = {
        "facebook": [
            "https://l.facebook.com/",
            "https://www.facebook.com/",
            None,
        ],
        "google_cpc": [
            "https://www.google.com/",
            "https://www.google.co.ke/",
        ],
        "google_organic": [
            "https://www.google.com/",
            "https://www.google.co.ke/",
            "https://www.bing.com/",
        ],
        "direct": [None],
        "newsletter": [
            None,
            "https://mail.google.com/",
        ],
        "partner_referral": [
            "https://smecommunity.example/",
            "https://accountants.example/",
            "https://directory.example/",
        ],
        "linkedin": [
            "https://www.linkedin.com/",
            "https://lnkd.in/",
        ],
    }

    if channel["source"] == "facebook":
        key = "facebook"
    elif channel["source"] == "google" and channel["medium"] == "cpc":
        key = "google_cpc"
    elif channel["source"] == "google":
        key = "google_organic"
    else:
        key = channel["source"] or "direct"

    choices = options.get(key, [None])
    return rng.choice(choices)


def generate_amount(rng):
    """
    Generate varied synthetic KES amounts.

    Most amounts are small; some are medium or large.
    These are simulated invoice/payment amounts, not benchmarks.
    """
    draw = rng.random()

    if draw < 0.70:
        amount = rng.lognormal(
            mean=np.log(1200),
            sigma=0.70,
        )
    elif draw < 0.94:
        amount = rng.lognormal(
            mean=np.log(6500),
            sigma=0.55,
        )
    else:
        amount = rng.lognormal(
            mean=np.log(25000),
            sigma=0.45,
        )

    amount = min(max(amount, 100), 100000)

    return int(max(100, round(amount / 10) * 10))


# ============================================================
# 4. DATASET GENERATION
# ============================================================

def generate_dataset(number_of_sessions, seed, as_of):
    """Generate sessions, orders and related application events."""
    rng = np.random.default_rng(seed)

    random.seed(seed)
    Faker.seed(seed)

    fake = Faker("en_KE")
    fake.seed_instance(seed)

    start = pd.Timestamp(as_of - pd.DateOffset(months=6))

    if start.tzinfo is None:
        start = start.tz_localize(TIMEZONE)
    else:
        start = start.tz_convert(TIMEZONE)

    session_times = generate_session_times(
        number_of_sessions,
        start,
        as_of,
        rng,
    )

    session_rows = []
    event_rows = []
    order_rows = []

    # The sequential order IDs simplify joins and database loading.
    next_order_id = 1

    # Some browser/client IDs recur across multiple sessions.
    existing_client_ids = []

    channel_weights = [channel["weight"] for channel in CHANNELS]

    for started_at in session_times:

        # ----------------------------------------------------
        # A. CREATE SESSION
        # ----------------------------------------------------

        channel = weighted_choice(
            rng,
            CHANNELS,
            channel_weights,
        )

        session_id = str(uuid.uuid4())

        mobile_share = channel["mobile_share"]
        remaining_share = 1.0 - mobile_share

        device = weighted_choice(
            rng,
            DEVICE_CATEGORIES,
            [
                mobile_share,
                remaining_share * 0.82,
                remaining_share * 0.18,
            ],
        )

        campaign = weighted_choice(
            rng,
            channel["campaigns"],
            channel["campaign_weights"],
        )

        landing_page = weighted_choice(
            rng,
            [
                "/",
                "/pricing",
                "/mpesa-reconciliation",
                "/invoice-management",
                "/demo",
                "/blog/mpesa-reconciliation-guide",
            ],
            [0.20, 0.22, 0.20, 0.16, 0.10, 0.12],
        )

        # Simulate returning visitors without real identities.
        if existing_client_ids and rng.random() < 0.28:
            client_id = str(rng.choice(existing_client_ids))
        else:
            client_number = int(
                rng.integers(100000000, 999999999)
            )

            client_id = (
                f"{client_number}.{int(started_at.timestamp())}"
            )

            existing_client_ids.append(client_id)

        session_rows.append({
            "session_id": session_id,
            "started_at": started_at,
            "utm_source": channel["source"],
            "utm_medium": channel["medium"],
            "utm_campaign": campaign,
            "landing_page": landing_page,
            "referrer": get_referrer(channel, rng),
            "device_category": device,
            "data_origin": "synthetic",
            "ga_client_id": client_id,
        })

        # ----------------------------------------------------
        # B. CREATE PAGE-VIEW EVENTS
        # ----------------------------------------------------

        first_page_time = min(
            started_at + pd.Timedelta(
                seconds=int(rng.integers(0, 4))
            ),
            as_of,
        )

        event_rows.append({
            "session_id": session_id,
            "event_name": "page_view",
            "order_id": None,
            "occurred_at": first_page_time,
            "event_source": "web",
            "properties": {
                "page_location": landing_page,
                "page_type": (
                    landing_page.strip("/").split("/")[-1] or "home"
                ),
                "is_landing_page": True,
                "device_category": device,
            },
        })

        # A proportion of sessions view additional pages.
        additional_views = int(
            rng.choice(
                [0, 1, 2, 3],
                p=[0.55, 0.32, 0.10, 0.03],
            )
        )

        latest_event_time = first_page_time

        other_pages = [
            "/pricing",
            "/mpesa-reconciliation",
            "/invoice-management",
            "/features/payment-tracking",
            "/demo",
            "/blog/invoice-tracking",
        ]

        page_weights = [0.22, 0.20, 0.19, 0.16, 0.11, 0.12]

        for _ in range(additional_views):

            latest_event_time = min(
                latest_event_time + pd.Timedelta(
                    seconds=int(rng.integers(8, 76))
                ),
                as_of,
            )

            other_page = weighted_choice(
                rng,
                other_pages,
                page_weights,
            )

            event_rows.append({
                "session_id": session_id,
                "event_name": "page_view",
                "order_id": None,
                "occurred_at": latest_event_time,
                "event_source": "web",
                "properties": {
                    "page_location": other_page,
                    "page_type": (
                        other_page.strip("/").split("/")[-1]
                    ),
                    "is_landing_page": False,
                    "device_category": device,
                },
            })

        # ----------------------------------------------------
        # C. CHECK WHETHER THE VISITOR STARTS CHECKOUT
        # ----------------------------------------------------

        checkout_probability = channel["checkout_rate"]

        if device == "mobile":
            checkout_probability *= 1.02
        elif device == "tablet":
            checkout_probability *= 0.93

        if rng.random() >= checkout_probability:
            continue

        begin_checkout_time = min(
            latest_event_time + pd.Timedelta(
                seconds=int(rng.integers(4, 46))
            ),
            as_of,
        )

        begin_event_index = len(event_rows)

        event_rows.append({
            "session_id": session_id,
            "event_name": "begin_checkout",
            "order_id": None,
            "occurred_at": begin_checkout_time,
            "event_source": "web",
            "properties": {
                "checkout_method": "mpesa_stk_push",
                "currency": "KES",
                "device_category": device,
            },
        })

        # Some sessions encounter an error before order creation.
        if rng.random() < 0.035:

            error_type = weighted_choice(
                rng,
                [
                    "client_validation",
                    "network_error",
                    "checkout_service_unavailable",
                ],
                [0.32, 0.48, 0.20],
            )

            error_time = min(
                begin_checkout_time + pd.Timedelta(
                    seconds=int(rng.integers(1, 8))
                ),
                as_of,
            )

            event_rows.append({
                "session_id": session_id,
                "event_name": "checkout_error",
                "order_id": None,
                "occurred_at": error_time,
                "event_source": "api",
                "properties": {
                    "error_type": error_type,
                    "stage": "before_order_creation",
                    "currency": "KES",
                },
            })

            continue

        # Some visitors abandon after checkout but before payment initiation.
        if rng.random() >= channel["initiation_rate"]:
            continue

        order_id = next_order_id
        next_order_id += 1

        event_rows[begin_event_index]["order_id"] = order_id

        initiated_at = min(
            begin_checkout_time + pd.Timedelta(
                seconds=int(rng.integers(2, 12))
            ),
            as_of,
        )

        event_rows.append({
            "session_id": session_id,
            "event_name": "payment_initiated",
            "order_id": order_id,
            "occurred_at": initiated_at,
            "event_source": "api",
            "properties": {
                "payment_method": "mpesa_stk_push",
                "currency": "KES",
                "source_system": "synthetic_checkout_api",
            },
        })

        # ----------------------------------------------------
        # D. SIMULATE THE M-PESA PAYMENT OUTCOME
        # ----------------------------------------------------

        pending_probability = 0.045
        outcome_draw = rng.random()

        if outcome_draw < pending_probability:

            # Pending means no terminal callback has been observed.
            status = "PENDING"
            result_code = None
            result_desc = None
            receipt_number = None

            updated_at = min(
                initiated_at + pd.Timedelta(
                    minutes=int(rng.integers(5, 46))
                ),
                as_of,
            )

        else:

            success_probability = channel["success_rate"]

            if device == "mobile":
                success_probability -= 0.015

            if rng.random() < success_probability:

                status = "SUCCESS"
                result_code = "0"
                result_desc = (
                    "The service request is processed successfully"
                )
                receipt_number = f"SYN{order_id:07d}"

            else:

                status = "FAILED"

                result_code, result_desc, _ = weighted_choice(
                    rng,
                    FAILURE_OUTCOMES,
                    [item[2] for item in FAILURE_OUTCOMES],
                )

                receipt_number = None

            callback_delay = int(rng.integers(4, 121))

            updated_at = min(
                initiated_at + pd.Timedelta(
                    seconds=callback_delay
                ),
                as_of,
            )

            if status == "SUCCESS":
                terminal_event_name = "payment_succeeded"
            else:
                terminal_event_name = "payment_failed"

            properties = {
                "payment_method": "mpesa_stk_push",
                "currency": "KES",
                "result_code": result_code,
            }

            if status == "SUCCESS":
                properties["synthetic_receipt"] = True
            else:
                properties["failure_reason"] = result_desc

            event_rows.append({
                "session_id": session_id,
                "event_name": terminal_event_name,
                "order_id": order_id,
                "occurred_at": updated_at,
                "event_source": "mpesa_callback",
                "properties": properties,
            })

        # ----------------------------------------------------
        # E. SAVE THE BUSINESS ORDER
        # ----------------------------------------------------

        amount = generate_amount(rng)

        # Synthetic Kenyan-format phone number.
        # It is stored in orders only, never in event properties.
        phone_number = fake.numerify(
            text="+2547########"
        )

        order_rows.append({
            "id": order_id,
            "session_id": session_id,
            "phone_number": phone_number,
            "amount": amount,
            "status": status,
            "checkout_request_id": f"SIM-CO-{order_id:08d}",
            "merchant_request_id": f"SIM-MR-{order_id:08d}",
            "result_code": result_code,
            "result_desc": result_desc,
            "mpesa_receipt_number": receipt_number,
            "created_at": initiated_at,
            "updated_at": updated_at,
        })

    # ========================================================
    # 5. CONVERT RECORDS INTO PANDAS DATAFRAMES
    # ========================================================

    sessions = pd.DataFrame(session_rows)

    orders = pd.DataFrame(
        order_rows,
        columns=[
            "id",
            "session_id",
            "phone_number",
            "amount",
            "status",
            "checkout_request_id",
            "merchant_request_id",
            "result_code",
            "result_desc",
            "mpesa_receipt_number",
            "created_at",
            "updated_at",
        ],
    )

    events = pd.DataFrame(
        event_rows,
        columns=[
            "session_id",
            "event_name",
            "order_id",
            "occurred_at",
            "event_source",
            "properties",
        ],
    )

    # Give every event a unique sequential ID.
    events = events.sort_values(
        ["occurred_at", "session_id", "event_name"],
        kind="stable",
    ).reset_index(drop=True)

    events.insert(
        0,
        "event_id",
        np.arange(1, len(events) + 1, dtype=np.int64),
    )

    events["order_id"] = pd.array(
        events["order_id"],
        dtype="Int64",
    )

    orders["id"] = pd.array(
        orders["id"],
        dtype="Int64",
    )

    if not orders.empty:
        orders["amount"] = orders["amount"].astype("int64")
    else:
        orders["amount"] = pd.Series(dtype="int64")

    # Convert Python dictionaries to valid JSON strings for CSV export.
    events["properties"] = events["properties"].map(
        lambda value: json.dumps(
            value or {},
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )

    # Make timestamp output consistent with the Nairobi timezone.
    for dataframe, columns in [
        (sessions, ["started_at"]),
        (events, ["occurred_at"]),
        (orders, ["created_at", "updated_at"]),
    ]:
        for column in columns:
            dataframe[column] = pd.to_datetime(
                dataframe[column],
                utc=True,
            ).dt.tz_convert(TIMEZONE)

    # ========================================================
    # 6. DATA QUALITY VALIDATION
    # ========================================================

    validate_dataset(sessions, events, orders, as_of)

    summary = build_summary(
        sessions,
        events,
        orders,
        start,
        as_of,
    )

    return sessions, events, orders, summary


# ============================================================
# 7. VALIDATE THE GENERATED DATA
# ============================================================

def validate_dataset(sessions, events, orders, as_of):
    """Stop execution if important data-quality rules fail."""

    session_ids = set(sessions["session_id"])

    order_ids = set(
        int(value)
        for value in orders["id"].dropna().tolist()
    )

    assert sessions["session_id"].is_unique
    assert sessions["data_origin"].eq("synthetic").all()

    assert sessions["started_at"].min() >= (
        as_of - pd.DateOffset(months=6) - pd.Timedelta(seconds=2)
    )

    assert sessions["started_at"].max() <= as_of

    assert events["event_id"].is_unique
    assert events["session_id"].isin(session_ids).all()

    referenced_order_ids = (
        events.loc[
            events["order_id"].notna(),
            "order_id",
        ]
        .astype("int64")
    )

    assert referenced_order_ids.isin(order_ids).all()

    assert orders["id"].is_unique
    assert orders["session_id"].isin(session_ids).all()
    assert (orders["amount"] > 0).all()

    assert orders["status"].isin(
        ["PENDING", "SUCCESS", "FAILED"]
    ).all()

    assert (orders["updated_at"] >= orders["created_at"]).all()
    assert events["occurred_at"].le(as_of).all()

    # Privacy check: phone numbers must not leak into analytics events.
    serialized_properties = events["properties"].astype(str).str.lower()

    assert not serialized_properties.str.contains(
        "phone_number"
    ).any()

    assert not serialized_properties.str.contains(
        r"\+2547\d{8}",
        regex=True,
    ).any()

    # Every order must have a payment_initiated event.
    initiated_ids = set(
        int(value)
        for value in events.loc[
            events["event_name"] == "payment_initiated",
            "order_id",
        ].dropna().tolist()
    )

    assert order_ids == initiated_ids

    succeeded_ids = set(
        int(value)
        for value in orders.loc[
            orders["status"] == "SUCCESS",
            "id",
        ].tolist()
    )

    failed_ids = set(
        int(value)
        for value in orders.loc[
            orders["status"] == "FAILED",
            "id",
        ].tolist()
    )

    pending_ids = set(
        int(value)
        for value in orders.loc[
            orders["status"] == "PENDING",
            "id",
        ].tolist()
    )

    event_success_ids = set(
        int(value)
        for value in events.loc[
            events["event_name"] == "payment_succeeded",
            "order_id",
        ].dropna().tolist()
    )

    event_failed_ids = set(
        int(value)
        for value in events.loc[
            events["event_name"] == "payment_failed",
            "order_id",
        ].dropna().tolist()
    )

    assert succeeded_ids == event_success_ids
    assert failed_ids == event_failed_ids

    assert not (succeeded_ids & failed_ids)
    assert not (pending_ids & (succeeded_ids | failed_ids))

    successful_orders = orders[
        orders["status"] == "SUCCESS"
    ]

    failed_orders = orders[
        orders["status"] == "FAILED"
    ]

    pending_orders = orders[
        orders["status"] == "PENDING"
    ]

    assert successful_orders["result_code"].eq("0").all()
    assert successful_orders["mpesa_receipt_number"].notna().all()

    assert failed_orders["result_code"].notna().all()
    assert failed_orders["mpesa_receipt_number"].isna().all()

    assert pending_orders["result_code"].isna().all()
    assert pending_orders["mpesa_receipt_number"].isna().all()


# ============================================================
# 8. BUILD A DATASET SUMMARY
# ============================================================

def build_summary(sessions, events, orders, start, end):

    successful_orders = orders[
        orders["status"] == "SUCCESS"
    ]

    channel_labels = (
        sessions["utm_source"].fillna("direct")
        + "/"
        + sessions["utm_medium"].fillna("none")
    )

    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "n_sessions": len(sessions),
        "n_events": len(events),
        "n_orders": len(orders),
        "distinct_clients": sessions["ga_client_id"].nunique(),
        "event_counts": events["event_name"].value_counts().to_dict(),
        "channel_sessions": channel_labels.value_counts().to_dict(),
        "order_status_counts": orders["status"].value_counts().to_dict(),
        "failure_reasons": (
            orders.loc[
                orders["status"] == "FAILED",
                "result_desc",
            ].value_counts().to_dict()
        ),
        "sessions_with_checkout": events.loc[
            events["event_name"] == "begin_checkout",
            "session_id",
        ].nunique(),
        "payment_initiations": int(
            (events["event_name"] == "payment_initiated").sum()
        ),
        "successful_orders": len(successful_orders),
        "successful_revenue_kes": int(
            successful_orders["amount"].sum()
        ),
        "successful_aov_kes": round(
            float(successful_orders["amount"].mean()), 2
        ) if not successful_orders.empty else 0,
    }


def write_summary(path, summary):
    lines = [
        "PROJECT 2 SYNTHETIC DATASET SUMMARY",
        "===================================",
        f"Time window: {summary['start']} to {summary['end']}",
        f"Sessions: {summary['n_sessions']:,}",
        f"Events: {summary['n_events']:,}",
        f"Orders: {summary['n_orders']:,}",
        f"Distinct synthetic client IDs: {summary['distinct_clients']:,}",
        f"Sessions with checkout: {summary['sessions_with_checkout']:,}",
        f"Payment initiations: {summary['payment_initiations']:,}",
        f"Successful orders: {summary['successful_orders']:,}",
        f"Successful revenue (KES): {summary['successful_revenue_kes']:,}",
        f"Successful-order AOV (KES): {summary['successful_aov_kes']:,.2f}",
        "",
        "Sessions by source/medium:",
    ]

    lines.extend(
        f"  - {key}: {value:,}"
        for key, value in summary["channel_sessions"].items()
    )

    lines.extend(["", "Event counts:"])

    lines.extend(
        f"  - {key}: {value:,}"
        for key, value in summary["event_counts"].items()
    )

    lines.extend(["", "Order status counts:"])

    lines.extend(
        f"  - {key}: {value:,}"
        for key, value in summary["order_status_counts"].items()
    )

    lines.extend(["", "Failure outcomes:"])

    lines.extend(
        f"  - {key}: {value:,}"
        for key, value in summary["failure_reasons"].items()
    )

    lines.extend([
        "",
        "IMPORTANT NOTES:",
        "- All data is synthetic.",
        "- Do not send the data to GA4 or M-Pesa.",
        "- Phone numbers appear only in orders.csv.",
        "- Event properties are JSON strings.",
        "- Import sessions first, orders second, and events third.",
    ])

    path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


# ============================================================
# 9. MAIN PROGRAM
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description="Generate Project 2 synthetic analytics data."
    )

    parser.add_argument(
        "--sessions",
        type=int,
        default=10000,
        help="Number of sessions; default 10000.",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility.",
    )

    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("project2_data"),
        help="Directory where generated files are saved.",
    )

    parser.add_argument(
        "--as-of",
        type=str,
        default=None,
        help="Optional ending date/time, for example 2026-10-26.",
    )

    args = parser.parse_args()

    if args.sessions < 1000:
        parser.error(
            "Use at least 1000 sessions; 10000 is recommended."
        )

    as_of = parse_as_of(args.as_of)

    args.out_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("Generating synthetic Project 2 data...")
    print(f"Requested sessions: {args.sessions:,}")
    print(f"Random seed: {args.seed}")

    sessions, events, orders, summary = generate_dataset(
        args.sessions,
        args.seed,
        as_of,
    )

    # Save each DataFrame to a CSV file.
    sessions.to_csv(
        args.out_dir / "analytics_sessions.csv",
        index=False,
        encoding="utf-8",
        date_format="%Y-%m-%d %H:%M:%S%z",
    )

    events.to_csv(
        args.out_dir / "analytics_events.csv",
        index=False,
        encoding="utf-8",
        date_format="%Y-%m-%d %H:%M:%S%z",
    )

    orders.to_csv(
        args.out_dir / "orders.csv",
        index=False,
        encoding="utf-8",
        date_format="%Y-%m-%d %H:%M:%S%z",
    )

    # Save the PostgreSQL table definitions.
    (
        args.out_dir / "00_create_source_tables.sql"
    ).write_text(
        SCHEMA_SQL,
        encoding="utf-8",
    )

    # Save counts and summary statistics.
    write_summary(
        args.out_dir / "dataset_summary.txt",
        summary,
    )

    print()
    print("SUCCESS: Dataset generated and validated.")
    print(f"Output folder: {args.out_dir.resolve()}")
    print(f"Sessions: {len(sessions):,}")
    print(f"Events: {len(events):,}")
    print(f"Orders: {len(orders):,}")
    print(f"Order statuses: {summary['order_status_counts']}")
    print(
        "Successful revenue (KES): "
        f"{summary['successful_revenue_kes']:,}"
    )
    print()
    print("Files generated:")
    print("  analytics_sessions.csv")
    print("  analytics_events.csv")
    print("  orders.csv")
    print("  00_create_source_tables.sql")
    print("  dataset_summary.txt")
    print()
    print("Import order:")
    print("  1. analytics_sessions.csv")
    print("  2. orders.csv")
    print("  3. analytics_events.csv")
    print()
    print("All records are synthetic.")


if __name__ == "__main__":
    main()