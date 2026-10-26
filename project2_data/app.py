import sys
import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine

# ---------------------------------------------------------
# 1. DATABASE CONNECTION CONFIGURATION
# ---------------------------------------------------------
DB_URI = "postgresql+pg8000://myuser:mypassword@localhost:5432/mydatabase"

@st.cache_data(ttl=60)
def load_data():
    engine = create_engine(DB_URI)
    query = "SELECT * FROM project2.mart_campaign_performance;"
    return pd.read_sql(query, engine)

st.set_page_config(
    page_title="SME SaaS Revenue Intelligence",
    layout="wide"
)

st.title("📊 SME SaaS Revenue & Funnel Performance")
st.markdown("Real-time telemetry and attribution intelligence connected to PostgreSQL.")

# ---------------------------------------------------------
# 2. LOAD DATA
# ---------------------------------------------------------
try:
    df = load_data()
except Exception as e:
    st.error(f"Failed to connect to PostgreSQL database: {e}")
    st.stop()
    sys.exit(1)

# ---------------------------------------------------------
# 3. TOP-LEVEL KPI METRICS
# ---------------------------------------------------------
total_revenue = df["total_revenue_kes"].sum()
total_sessions = df["total_sessions"].sum()
total_orders = df["successful_orders"].sum()
overall_aov = total_revenue / total_orders if total_orders > 0 else 0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Revenue (KES)", f"{total_revenue:,.2f}")
col2.metric("Total Sessions", f"{total_sessions:,}")
col3.metric("Successful Orders", f"{total_orders:,}")
col4.metric("Average Order Value (KES)", f"{overall_aov:,.2f}")

st.divider()

# ---------------------------------------------------------
# 4. VISUALIZATIONS
# ---------------------------------------------------------
chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.subheader("Revenue by Acquisition Channel")
    fig_rev = px.bar(
        df,
        x="utm_source",
        y="total_revenue_kes",
        color="utm_medium",
        title="Total Revenue (KES) per Channel Source",
        labels={"total_revenue_kes": "Revenue (KES)", "utm_source": "Source"},
        text_auto=".2s"
    )
    st.plotly_chart(fig_rev, use_container_width=True)

with chart_col2:
    st.subheader("Checkout vs Payment Success Rate (%)")
    fig_rates = px.scatter(
        df,
        x="checkout_start_rate_pct",
        y="payment_success_rate_pct",
        size="total_sessions",
        color="utm_source",
        hover_name="utm_campaign",
        title="Funnel Efficiency Matrix",
        labels={
            "checkout_start_rate_pct": "Checkout Start Rate (%)",
            "payment_success_rate_pct": "Payment Success Rate (%)"
        }
    )
    st.plotly_chart(fig_rates, use_container_width=True)

# ---------------------------------------------------------
# 5. DETAILED DATA TABLE
# ---------------------------------------------------------
st.subheader("Campaign Performance Data Mart")
st.dataframe(df, use_container_width=True)