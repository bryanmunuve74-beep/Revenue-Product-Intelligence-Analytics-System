-- One row per successful, receipt-backed business order.
-- This is a VIEW, not a physically stored table: it stays consistent with orders.
CREATE OR REPLACE VIEW project2.fct_verified_purchases AS
SELECT
    o.order_id,
    o.session_id,
    s.utm_source,
    s.utm_medium,
    s.utm_campaign,
    s.device_category,
    o.amount,
    o.mpesa_receipt_number,
    o.created_at AS purchase_time,
    o.order_date
FROM project2.stg_orders AS o
JOIN project2.stg_sessions AS s ON s.session_id = o.session_id
WHERE o.status = 'SUCCESS'
  AND o.result_code = '0'
  AND o.mpesa_receipt_number IS NOT NULL;

-- One row per source / medium / campaign combination.
-- Numerators and denominators are aggregated separately to avoid join fan-out.
CREATE OR REPLACE VIEW project2.mart_campaign_performance AS
WITH session_summary AS (
    SELECT utm_source, utm_medium, utm_campaign,
           COUNT(DISTINCT session_id) AS total_sessions
    FROM project2.stg_sessions
    GROUP BY utm_source, utm_medium, utm_campaign
),
checkout_summary AS (
    SELECT s.utm_source, s.utm_medium, s.utm_campaign,
           COUNT(DISTINCT e.session_id) AS checkout_sessions
    FROM project2.stg_events AS e
    JOIN project2.stg_sessions AS s ON s.session_id = e.session_id
    WHERE e.event_name = 'begin_checkout'
    GROUP BY s.utm_source, s.utm_medium, s.utm_campaign
),
attempt_summary AS (
    SELECT s.utm_source, s.utm_medium, s.utm_campaign,
           COUNT(DISTINCT e.order_id) AS payment_attempts
    FROM project2.stg_events AS e
    JOIN project2.stg_sessions AS s ON s.session_id = e.session_id
    WHERE e.event_name = 'payment_initiated'
      AND e.order_id IS NOT NULL
    GROUP BY s.utm_source, s.utm_medium, s.utm_campaign
),
revenue_summary AS (
    SELECT utm_source, utm_medium, utm_campaign,
           COUNT(DISTINCT order_id) AS successful_orders,
           SUM(amount) AS total_revenue_kes,
           AVG(amount) AS aov_kes
    FROM project2.fct_verified_purchases
    GROUP BY utm_source, utm_medium, utm_campaign
)
SELECT
    ss.utm_source,
    ss.utm_medium,
    ss.utm_campaign,
    ss.total_sessions,
    COALESCE(cs.checkout_sessions, 0) AS checkout_sessions,
    COALESCE(at.payment_attempts, 0) AS payment_attempts,
    COALESCE(rs.successful_orders, 0) AS successful_orders,
    COALESCE(rs.total_revenue_kes, 0)::NUMERIC(14, 2) AS total_revenue_kes,
    ROUND(100.0 * COALESCE(cs.checkout_sessions, 0) / NULLIF(ss.total_sessions, 0), 2) AS checkout_start_rate_pct,
    ROUND(100.0 * COALESCE(rs.successful_orders, 0) / NULLIF(at.payment_attempts, 0), 2) AS payment_success_rate_pct,
    ROUND(rs.aov_kes, 2) AS aov_kes
FROM session_summary AS ss
LEFT JOIN checkout_summary AS cs USING (utm_source, utm_medium, utm_campaign)
LEFT JOIN attempt_summary AS at USING (utm_source, utm_medium, utm_campaign)
LEFT JOIN revenue_summary AS rs USING (utm_source, utm_medium, utm_campaign);

-- Daily verified revenue supports trend charts and does not use browser events as revenue.
CREATE OR REPLACE VIEW project2.mart_daily_revenue AS
SELECT order_date, COUNT(DISTINCT order_id) AS successful_orders,
       SUM(amount)::NUMERIC(14, 2) AS verified_revenue_kes,
       ROUND(AVG(amount), 2) AS aov_kes
FROM project2.fct_verified_purchases
GROUP BY order_date;
