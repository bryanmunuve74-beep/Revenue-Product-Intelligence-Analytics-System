# SME SaaS Revenue & Funnel Analytics Pipeline

An end-to-end containerized data pipeline and interactive analytics dashboard built using PostgreSQL, Docker, and Streamlit. The system ingests web session logs and M-Pesa order events, transforms raw telemetry into analytical SQL marts, and presents real-time funnel conversion metrics.

## 🛠️ Architecture & Tech Stack

* **Database & Infrastructure:** PostgreSQL 15, Docker, Docker Compose
* **Data Modeling & Analytics:** SQL (Staging Views, Fact Tables, Campaign Marts), DBeaver
* **Backend Engine:** Python 3.14, SQLAlchemy, pg8000 (Pure Python Driver)
* **Visualization:** Streamlit, Plotly Express

## 📐 Data Pipeline & SQL Mart Structure

1. **Staging Layer (`project2.stg_*`):** Standardizes raw session entries, transactional orders, and web event streams.
2. **Fact Layer (`project2.fct_verified_purchases`):** Isolates verified successful payments (`status = 'SUCCESS'`) as the single source of truth for revenue.
3. **Analytics Mart (`project2.mart_campaign_performance`):** Calculates key business KPIs per channel:
   * **Checkout Start Rate (%)**
   * **M-Pesa Payment Success Rate (%)**
   * **Average Order Value (KES)**

## 🚀 Local Setup & Execution

### 1. Launch PostgreSQL Container
```bash
docker-compose up -d