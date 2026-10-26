-- Active: 1792294524258@@127.0.0.1@5432@mydatabase
-- Active: 1792294524258@@127.0.0.1@5432@postgres

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
