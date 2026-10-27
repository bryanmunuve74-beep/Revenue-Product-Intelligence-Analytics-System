CREATE SCHEMA IF NOT EXISTS project2;

CREATE OR REPLACE VIEW project2.stg_sessions AS
SELECT 
    session_id,
    COALESCE(utm_source, 'direct') AS utm_source,
    COALESCE(utm_medium, '(none)') AS utm_medium,
    COALESCE(utm_campaign, '(none)') AS utm_campaign,
    device_category,
    created_at::date AS session_date,
    created_at
FROM project2.analytics_sessions;

CREATE OR REPLACE VIEW project2.stg_orders AS
SELECT 
    id AS order_id,
    session_id,
    amount,
    status,
    merchant_request_id,
    checkout_request_id,
    result_code,
    mpesa_receipt_number,
    created_at::date AS order_date,
    created_at
FROM project2.orders;

CREATE OR REPLACE VIEW project2.stg_events AS
SELECT 
    event_id,
    session_id,
    event_name,
    event_properties,
    created_at
FROM project2.analytics_events;