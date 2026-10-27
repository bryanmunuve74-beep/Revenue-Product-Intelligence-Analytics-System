# Data dictionary

All data in this project is generated synthetically. `phone_number` contains a non-routable `SYNTHETIC-KE-...` label, not a real phone number. Do not send these records to M-Pesa or GA4.

## `project2.analytics_sessions`

One row per simulated browser session. `session_id` is the session primary key and joins to events and orders. `started_at` is timezone-aware. UTM fields describe the simulated session acquisition source, medium, and campaign. `data_origin` is always `synthetic`. `ga_client_id` is a fabricated visitor identifier, not a real GA4 identity.

## `project2.analytics_events`

One row per simulated event. `event_id` is the event primary key. `session_id` references the session. `order_id` is nullable because page views and abandoned checkout events might not relate to an order; where present, it references the business order. `properties` is JSONB with optional event attributes. `event_source` labels `web`, `api`, or `mpesa_callback` in this simulation.

## `project2.orders`

One row per simulated payment attempt/order. `id` is the order primary key. `session_id` ties the order to its originating session. `amount` is a simulated positive KES amount. `status` is `SUCCESS`, `FAILED`, or `PENDING`. Successful rows must have result code `0` and a synthetic receipt. Failed rows have a result code but no receipt. Pending rows have no terminal result code or receipt.

## Analytical objects

- `stg_sessions`, `stg_orders`, `stg_events`: views that standardize and expose source fields; they preserve the underlying source records.
- `fct_verified_purchases`: view with one row per successful, receipt-backed order. Despite the `fct_` name, this is a view rather than a physical table.
- `mart_campaign_performance`: one row per source / medium / campaign with funnel counts and calculated rates.
- `mart_daily_revenue`: daily aggregation from verified purchase records.
