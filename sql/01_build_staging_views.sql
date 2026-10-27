-- Staging views standardize raw source values and expose useful derived fields.
-- They do not delete source rows or decide which purchases count as revenue.
CREATE SCHEMA IF NOT EXISTS project2;

CREATE OR REPLACE VIEW project2.stg_sessions AS
SELECT
    session_id,
    started_at,
    (started_at AT TIME ZONE 'Africa/Nairobi')::date AS session_date,
    COALESCE(NULLIF(BTRIM(utm_source), ''), 'direct') AS utm_source,
    COALESCE(NULLIF(BTRIM(utm_medium), ''), '(none)') AS utm_medium,
    COALESCE(NULLIF(BTRIM(utm_campaign), ''), '(none)') AS utm_campaign,
    landing_page,
    referrer,
    device_category,
    data_origin,
    ga_client_id
FROM project2.analytics_sessions;

CREATE OR REPLACE VIEW project2.stg_orders AS
SELECT
    id AS order_id,
    session_id,
    amount::NUMERIC(12, 2) AS amount,
    UPPER(BTRIM(status)) AS status,
    checkout_request_id,
    merchant_request_id,
    result_code,
    result_desc,
    mpesa_receipt_number,
    created_at,
    updated_at,
    (created_at AT TIME ZONE 'Africa/Nairobi')::date AS order_date,
    EXTRACT(EPOCH FROM (updated_at - created_at))::NUMERIC(12, 2) AS processing_duration_seconds,
    (UPPER(BTRIM(status)) = 'SUCCESS' AND result_code = '0' AND mpesa_receipt_number IS NOT NULL) AS is_verified_success
FROM project2.orders;

CREATE OR REPLACE VIEW project2.stg_events AS
SELECT
    event_id,
    session_id,
    event_name,
    order_id,
    occurred_at,
    (occurred_at AT TIME ZONE 'Africa/Nairobi')::date AS event_date,
    event_source,
    properties,
    properties ->> 'page_location' AS page_location,
    properties ->> 'checkout_method' AS checkout_method,
    properties ->> 'error_type' AS error_type,
    properties ->> 'failure_reason' AS failure_reason,
    properties ->> 'result_code' AS event_result_code
FROM project2.analytics_events;
