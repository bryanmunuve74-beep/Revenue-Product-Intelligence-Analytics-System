# Metric definitions

These definitions apply to the generated six-month dataset unless a dashboard date filter is explicitly applied.

| Metric | Definition | Important qualification |
|---|---|---|
| Total sessions | Count of distinct `session_id` in `stg_sessions` | A session is not the same as a person. |
| Checkout-start rate | Distinct sessions containing `begin_checkout` / distinct sessions × 100 | The numerator is a session count, not event count. |
| Payment attempts | Distinct non-null `order_id` values for `payment_initiated` events | The synthetic model has one order per attempt. A production schema may need a separate attempt identifier. |
| Payment success rate | Count of verified successful order IDs / distinct payment attempts × 100 | A pending attempt is not silently recoded as a failure; it remains in the attempt denominator until the chosen reporting policy says otherwise. |
| Verified revenue | Sum of `amount` for `fct_verified_purchases` | Success status, result code `0`, and a non-null receipt are all required. |
| Average order value (AOV) | Verified revenue / count of verified successful orders | Failed and pending orders do not contribute to the numerator or denominator. |
| Processing duration | `updated_at - created_at` in seconds | For pending orders, this is the time between initiation and the current simulated update, not proof of a final resolution. |

## Reconciliation principle

Business order records are the revenue source of truth. Browser/backend events describe funnel behavior and are reconciled against order records. An event alone must not create revenue.
