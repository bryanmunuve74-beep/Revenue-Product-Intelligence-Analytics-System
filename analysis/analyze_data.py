"""Independent Pandas analysis and SQL-mart reconciliation (M6)."""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_URL = "postgresql+pg8000://p2_user:p2_dev_only_password@localhost:5433/project2_analytics"


def main() -> None:
    load_dotenv(ROOT / ".env")
    engine = create_engine(os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL), pool_pre_ping=True)
    try:
        sessions = pd.read_sql(text("SELECT session_id, utm_source, utm_medium, utm_campaign FROM project2.stg_sessions"), engine)
        events = pd.read_sql(text("SELECT session_id, order_id, event_name FROM project2.stg_events"), engine)
        purchases = pd.read_sql(text("SELECT order_id, utm_source, utm_medium, utm_campaign, amount, order_date FROM project2.fct_verified_purchases"), engine)
        sql_mart = pd.read_sql(text("SELECT * FROM project2.mart_campaign_performance"), engine)

        dims = ["utm_source", "utm_medium", "utm_campaign"]
        sessions[dims] = sessions[dims].fillna({"utm_source": "direct", "utm_medium": "(none)", "utm_campaign": "(none)"})
        events = events.merge(sessions[["session_id", *dims]], on="session_id", how="left", validate="many_to_one")

        session_counts = sessions.groupby(dims, dropna=False).agg(total_sessions=("session_id", "nunique")).reset_index()
        checkout_counts = (
            events.loc[events.event_name.eq("begin_checkout")]
            .groupby(dims, dropna=False).agg(checkout_sessions=("session_id", "nunique")).reset_index()
        )
        attempt_counts = (
            events.loc[events.event_name.eq("payment_initiated") & events.order_id.notna()]
            .groupby(dims, dropna=False).agg(payment_attempts=("order_id", "nunique")).reset_index()
        )
        revenue_counts = (
            purchases.groupby(dims, dropna=False)
            .agg(successful_orders=("order_id", "nunique"), total_revenue_kes=("amount", "sum"), aov_kes=("amount", "mean"))
            .reset_index()
        )
        py_mart = session_counts.merge(checkout_counts, on=dims, how="left").merge(attempt_counts, on=dims, how="left").merge(revenue_counts, on=dims, how="left")
        for col in ["checkout_sessions", "payment_attempts", "successful_orders", "total_revenue_kes"]:
            py_mart[col] = py_mart[col].fillna(0)
        py_mart["checkout_start_rate_pct"] = np.where(py_mart.total_sessions > 0, 100 * py_mart.checkout_sessions / py_mart.total_sessions, np.nan)
        py_mart["payment_success_rate_pct"] = np.where(py_mart.payment_attempts > 0, 100 * py_mart.successful_orders / py_mart.payment_attempts, np.nan)
        py_mart["aov_kes"] = np.where(py_mart.successful_orders > 0, py_mart.total_revenue_kes / py_mart.successful_orders, np.nan)

        merged = py_mart.merge(sql_mart, on=dims, suffixes=("_pandas", "_sql"), validate="one_to_one")
        for metric in ["total_sessions", "checkout_sessions", "payment_attempts", "successful_orders", "total_revenue_kes", "checkout_start_rate_pct", "payment_success_rate_pct", "aov_kes"]:
            left = pd.to_numeric(merged[f"{metric}_pandas"], errors="coerce").to_numpy(dtype=float)
            right = pd.to_numeric(merged[f"{metric}_sql"], errors="coerce").to_numpy(dtype=float)
            np.testing.assert_allclose(left, right, rtol=1e-7, atol=0.02, equal_nan=True, err_msg=f"Mismatch in {metric}")

        output = ROOT / "analysis" / "output"
        output.mkdir(parents=True, exist_ok=True)
        py_mart.sort_values("total_revenue_kes", ascending=False).to_csv(output / "campaign_analysis_pandas.csv", index=False)
        purchases.groupby("order_date", dropna=False).agg(successful_orders=("order_id", "nunique"), verified_revenue_kes=("amount", "sum"), aov_kes=("amount", "mean")).reset_index().to_csv(output / "daily_revenue_pandas.csv", index=False)

        total_sessions = len(sessions)
        checkout_sessions = events.loc[events.event_name.eq("begin_checkout"), "session_id"].nunique()
        payment_attempts = events.loc[events.event_name.eq("payment_initiated"), "order_id"].nunique()
        total_verified_orders = purchases.order_id.nunique()
        revenue = purchases.amount.sum()
        aov = purchases.amount.mean() if len(purchases) else 0
        print("Pandas analysis completed; SQL-mart reconciliation PASSED.")
        print(f"Sessions: {total_sessions:,}")
        print(f"Checkout-start rate: {checkout_sessions / total_sessions * 100:.2f}%")
        print(f"Payment success rate: {total_verified_orders / payment_attempts * 100:.2f}%" if payment_attempts else "Payment success rate: N/A")
        print(f"Verified purchases: {total_verified_orders:,}")
        print(f"Verified revenue (KES): {revenue:,.2f}")
        print(f"AOV (KES): {aov:,.2f}")
        print(f"CSV outputs: {output}")
    finally:
        engine.dispose()

if __name__ == "__main__":
    main()
