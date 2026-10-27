-- Every query below should return zero unless otherwise noted.

-- Sessions that do not have a source row (should always be zero because of FK).
SELECT COUNT(*) AS orders_without_session
FROM project2.orders o LEFT JOIN project2.analytics_sessions s USING (session_id)
WHERE s.session_id IS NULL;

SELECT COUNT(*) AS events_without_session
FROM project2.analytics_events e LEFT JOIN project2.analytics_sessions s USING (session_id)
WHERE s.session_id IS NULL;

SELECT COUNT(*) AS events_with_missing_order
FROM project2.analytics_events e LEFT JOIN project2.orders o ON o.id = e.order_id
WHERE e.order_id IS NOT NULL AND o.id IS NULL;

-- Status / receipt checks.
SELECT COUNT(*) AS invalid_success_orders
FROM project2.orders
WHERE status = 'SUCCESS' AND (result_code <> '0' OR mpesa_receipt_number IS NULL);

SELECT COUNT(*) AS pending_orders_with_terminal_fields
FROM project2.orders
WHERE status = 'PENDING' AND (result_code IS NOT NULL OR mpesa_receipt_number IS NOT NULL);

-- Count business orders and verified fact rows. The counts can legitimately differ.
SELECT status, COUNT(*) AS order_count, COALESCE(SUM(amount), 0) AS gross_order_value_kes
FROM project2.orders GROUP BY status ORDER BY status;

SELECT COUNT(*) AS verified_purchase_rows,
       COUNT(DISTINCT order_id) AS distinct_verified_orders,
       COALESCE(SUM(amount), 0) AS verified_revenue_kes
FROM project2.fct_verified_purchases;

-- Event/order disagreements for terminal payments. Expected zero for this simulated dataset.
SELECT COUNT(*) AS success_event_order_mismatches
FROM project2.orders o
FULL OUTER JOIN (
    SELECT DISTINCT order_id FROM project2.analytics_events WHERE event_name = 'payment_succeeded'
) e ON e.order_id = o.id
WHERE (o.status = 'SUCCESS') IS DISTINCT FROM (e.order_id IS NOT NULL);

SELECT COUNT(*) AS failure_event_order_mismatches
FROM project2.orders o
FULL OUTER JOIN (
    SELECT DISTINCT order_id FROM project2.analytics_events WHERE event_name = 'payment_failed'
) e ON e.order_id = o.id
WHERE (o.status = 'FAILED') IS DISTINCT FROM (e.order_id IS NOT NULL);
