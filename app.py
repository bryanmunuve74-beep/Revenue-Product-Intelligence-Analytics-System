"""Streamlit dashboard for Project 2 revenue and product intelligence."""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parent
DEFAULT_DATABASE_URL = "postgresql+pg8000://p2_user:p2_dev_only_password@localhost:5433/project2_analytics"
load_dotenv(ROOT / ".env")

st.set_page_config(page_title="SME SaaS Revenue Intelligence", page_icon="📊", layout="wide")
st.title("SME SaaS Revenue & Product Intelligence")
st.caption("Synthetic portfolio dataset · Revenue comes from verified order records, not analytics events.")


@st.cache_resource
def get_engine():
    return create_engine(os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL), pool_pre_ping=True)


@st.cache_data(ttl=60)
def load_campaign_mart() -> pd.DataFrame:
    return pd.read_sql(text("SELECT * FROM project2.mart_campaign_performance"), get_engine())


@st.cache_data(ttl=60)
def load_daily_revenue(start_date, end_date) -> pd.DataFrame:
    return pd.read_sql(text("""
        SELECT order_date, successful_orders, verified_revenue_kes, aov_kes
        FROM project2.mart_daily_revenue
        WHERE order_date BETWEEN :start_date AND :end_date
        ORDER BY order_date
    """), get_engine(), params={"start_date": start_date, "end_date": end_date})


@st.cache_data(ttl=60)
def load_order_health(start_date, end_date) -> pd.DataFrame:
    return pd.read_sql(text("""
        SELECT status, COUNT(*) AS order_count, COALESCE(SUM(amount), 0) AS order_value_kes
        FROM project2.stg_orders
        WHERE order_date BETWEEN :start_date AND :end_date
        GROUP BY status ORDER BY status
    """), get_engine(), params={"start_date": start_date, "end_date": end_date})


try:
    mart = load_campaign_mart()
    if mart.empty:
        st.warning("The campaign mart is empty. Generate, load, and transform the data first.")
        st.stop()
except Exception as exc:
    st.error("Could not load the analytics mart. Confirm PostgreSQL is running and apply sql/00_create_source_tables.sql, sql/01_build_staging_views.sql, and sql/02_build_analytics_marts.sql.")
    st.code(str(exc))
    st.stop()

# Revenue mart's date filters are applied to the daily facts; channel mart metrics are full-period.
left, right = st.columns([1, 2])
with left:
    selected_source = st.selectbox("Acquisition source", ["All sources", *sorted(mart.utm_source.dropna().unique().tolist())])
with right:
    st.info("Campaign and funnel metrics below use the complete simulated six-month dataset. The date filter in Revenue Health applies to daily verified revenue and order-state counts.")

campaign_view = mart.copy()
if selected_source != "All sources":
    campaign_view = campaign_view[campaign_view.utm_source == selected_source]

# Aggregates recompute from counts/sums so selected-channel KPIs have correct denominators.
sessions_total = int(campaign_view.total_sessions.sum())
checkout_total = int(campaign_view.checkout_sessions.sum())
attempts_total = int(campaign_view.payment_attempts.sum())
success_total = int(campaign_view.successful_orders.sum())
revenue_total = float(campaign_view.total_revenue_kes.sum())
aov_total = revenue_total / success_total if success_total else 0.0
checkout_rate = checkout_total / sessions_total * 100 if sessions_total else 0.0
success_rate = success_total / attempts_total * 100 if attempts_total else 0.0

overview, acquisition, revenue_health = st.tabs(["Overview", "Acquisition Funnel", "Revenue Health"])

with overview:
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Verified revenue", f"KES {revenue_total:,.0f}")
    k2.metric("Sessions", f"{sessions_total:,}")
    k3.metric("Successful orders", f"{success_total:,}")
    k4.metric("Average order value", f"KES {aov_total:,.0f}")
    st.subheader("Verified revenue by acquisition campaign")
    revenue_chart = campaign_view.sort_values("total_revenue_kes", ascending=False)
    fig = px.bar(revenue_chart, x="utm_campaign", y="total_revenue_kes", color="utm_source", hover_data=["successful_orders", "aov_kes"], labels={"utm_campaign": "Campaign", "total_revenue_kes": "Verified revenue (KES)", "utm_source": "Source"})
    fig.update_layout(template="plotly_dark", xaxis_tickangle=-30)
    st.plotly_chart(fig, use_container_width=True)

with acquisition:
    a1, a2 = st.columns(2)
    a1.metric("Checkout-start rate", f"{checkout_rate:.2f}%", help="Distinct sessions with begin_checkout / distinct sessions.")
    a2.metric("Payment success rate", f"{success_rate:.2f}%", help="Verified successful orders / distinct payment attempts.")
    display_cols = ["utm_source", "utm_medium", "utm_campaign", "total_sessions", "checkout_sessions", "checkout_start_rate_pct", "payment_attempts", "successful_orders", "payment_success_rate_pct", "total_revenue_kes", "aov_kes"]
    funnel_fig = px.funnel(pd.DataFrame({"Stage": ["Sessions", "Checkout sessions", "Payment attempts", "Successful orders"], "Count": [sessions_total, checkout_total, attempts_total, success_total]}), x="Count", y="Stage", title="Distinct funnel entities (counts; stages use different entities)")
    funnel_fig.update_layout(template="plotly_dark")
    st.plotly_chart(funnel_fig, use_container_width=True)
    st.dataframe(campaign_view[display_cols].sort_values("total_sessions", ascending=False), use_container_width=True, hide_index=True)

with revenue_health:
    date_default = (pd.Timestamp.now().date() - pd.Timedelta(days=183), pd.Timestamp.now().date())
    selected_dates = st.date_input("Revenue date range", value=date_default)
    if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
        date_start, date_end = selected_dates
    else:
        date_start = date_end = selected_dates
    daily = load_daily_revenue(date_start, date_end)
    health = load_order_health(date_start, date_end)
    if daily.empty:
        st.info("No verified purchases in this date range.")
    else:
        fig_daily = px.line(daily, x="order_date", y="verified_revenue_kes", markers=True, labels={"order_date": "Date", "verified_revenue_kes": "Verified revenue (KES)"}, title="Daily verified revenue")
        fig_daily.update_layout(template="plotly_dark")
        st.plotly_chart(fig_daily, use_container_width=True)
    st.subheader("Payment lifecycle health")
    st.dataframe(health, use_container_width=True, hide_index=True)
    st.caption("PENDING means no terminal outcome is recorded; it is not automatically counted as a failure.")
