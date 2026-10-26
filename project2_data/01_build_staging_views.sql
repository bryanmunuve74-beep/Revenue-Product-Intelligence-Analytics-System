-- Set search path to our project schema
SET search_path TO project2;

-- 1. STAGING SESSIONS
CREATE OR REPLACE VIEW project2.stg_sessions AS
SELECT
    session_id,
    started_at,
    COALESCE(utm_source, 'direct') AS utm_source,
    COALESCE(utm_medium, '(none)') AS utm_medium,
    COALESCE(utm_campaign, '(none)') AS utm_campaign,
    landing_page,
    referrer,
    device_category,
    ga_client_id,
    started_at::date AS session_date
FROM project2.analytics_sessions;

-- 2. STAGING ORDERS
CREATE OR REPLACE VIEW project2.stg_orders AS
SELECT
    id AS order_id,
    session_id,
    amount,
    status,
    checkout_request_id,
    merchant_request_id,
    result_code,
    result_desc,
    mpesa_receipt_number,
    created_at,
    updated_at,
    created_at::date AS order_date,
    EXTRACT(EPOCH FROM (updated_at - created_at)) AS processing_duration_seconds,
    CASE 
        WHEN status = 'SUCCESS' THEN TRUE 
        ELSE FALSE 
    END AS is_successful
FROM project2.orders;

-- 3. STAGING EVENTS (Parsing JSON properties)
CREATE OR REPLACE VIEW project2.stg_events AS
SELECT
    event_id,
    session_id,
    order_id,
    event_name,
    event_source,
    occurred_at,
    occurred_at::date AS event_date,
    properties->>'page_location' AS page_location,
    properties->>'checkout_method' AS checkout_method,
    properties->>'error_type' AS error_type,
    properties->>'failure_reason' AS failure_reason
FROM project2.analytics_events;