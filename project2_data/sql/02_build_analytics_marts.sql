SET search_path TO project2;

-- FACT TABLE: VERIFIED PURCHASES
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
FROM project2.stg_orders o
JOIN project2.stg_sessions s ON o.session_id = s.session_id
WHERE o.status = 'SUCCESS';

-- MART: CAMPAIGN PERFORMANCE & FUNNEL METRICS
CREATE OR REPLACE VIEW project2.mart_campaign_performance AS
WITH session_summary AS (
    SELECT
        s.utm_source,
        s.utm_medium,
        s.utm_campaign,
        COUNT(DISTINCT s.session_id) AS total_sessions,
        COUNT(DISTINCT CASE WHEN e.event_name = 'begin_checkout' THEN s.session_id END) AS checkout_sessions,
        COUNT(DISTINCT CASE WHEN e.event_name = 'payment_initiated' THEN s.session_id END) AS initiated_sessions
    FROM project2.stg_sessions s
    LEFT JOIN project2.stg_events e ON s.session_id = e.session_id
    GROUP BY 1, 2, 3
),
revenue_summary AS (
    SELECT
        utm_source,
        utm_medium,
        utm_campaign,
        COUNT(DISTINCT order_id) AS successful_orders,
        SUM(amount) AS total_revenue_kes
    FROM project2.fct_verified_purchases
    GROUP BY 1, 2, 3
)
SELECT
    ss.utm_source,
    ss.utm_medium,
    ss.utm_campaign,
    ss.total_sessions,
    ss.checkout_sessions,
    ss.initiated_sessions,
    COALESCE(rs.successful_orders, 0) AS successful_orders,
    COALESCE(rs.total_revenue_kes, 0) AS total_revenue_kes,
    ROUND((ss.checkout_sessions::numeric / NULLIF(ss.total_sessions, 0)) * 100, 2) AS checkout_start_rate_pct,
    ROUND((COALESCE(rs.successful_orders, 0)::numeric / NULLIF(ss.initiated_sessions, 0)) * 100, 2) AS payment_success_rate_pct,
    ROUND(COALESCE(rs.total_revenue_kes, 0)::numeric / NULLIF(rs.successful_orders, 0), 2) AS aov_kes
FROM session_summary ss
LEFT JOIN revenue_summary rs 
    ON ss.utm_source = rs.utm_source 
   AND ss.utm_medium = rs.utm_medium 
   AND ss.utm_campaign = rs.utm_campaign
ORDER BY total_revenue_kes DESC;