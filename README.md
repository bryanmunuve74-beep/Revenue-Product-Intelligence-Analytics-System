# SME SaaS Revenue & Product Intelligence Analytics System

A portfolio project simulating a Kenyan SME SaaS product that helps businesses reconcile M-Pesa payments with invoices. It demonstrates a reproducible synthetic-data pipeline, PostgreSQL modeling, revenue reconciliation, SQL metrics, Pandas analysis, a Streamlit/Plotly dashboard, and automated checks.

**All data is synthetic.** The generator does not connect to M-Pesa or GA4. `orders.phone_number` is a non-routable `SYNTHETIC-KE-...` identifier, not a real phone number. The Compose setup uses a separate database, volume, container name and host port so it does not intentionally reuse Project 1's PostgreSQL service.

## Architecture

1. `generate_mock_data.py` creates three CSVs: sessions, events, and orders. A fixed seed and fixed `--as-of` date make the same generation reproducible.
2. `docker-compose.yml` runs PostgreSQL on host port `5433` by default.
3. `load_data.py` creates the source schema if needed, loads source rows in foreign-key-safe order, and checks row counts and relationships.
4. SQL views in `sql/` standardize raw rows, define verified purchases, and calculate campaign and daily revenue marts.
5. `analysis/analyze_data.py` uses Pandas to independently calculate campaign metrics and compare them with SQL mart outputs.
6. `app.py` provides three dashboard views: Overview, Acquisition Funnel, and Revenue Health.
7. `pytest` runs generation, relationship, status, privacy, and reproducibility tests; GitHub Actions runs these tests on pushes and pull requests.

## Windows / PowerShell quick start

### 1. Create an environment and install packages

From the repository root:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
Copy-Item .env.example .env
```

If PowerShell blocks activation, run the Python executable directly as `.\.venv\Scripts\python.exe` instead.

### 2. Start the separate Project 2 database

```powershell
docker compose up -d db
docker compose ps
```

This uses host port `5433`, database `project2_analytics`, container `project2-postgres`, and volume `project2_postgres_data` by default. These are local-development credentials only. Change the `.env` credentials for any shared or deployed environment. Do not point `DATABASE_URL` at Project 1.

### 3. Generate data reproducibly

```powershell
py generate_mock_data.py --sessions 10000 --seed 42 --as-of 2026-10-27 --out-dir data
```

The fixed `--as-of` date makes the six-month date window reproducible. Omit it for a window ending at the current Nairobi date/time. Generated files are ignored by Git under `data/` so you do not accidentally commit newly generated data.

### 4. Load the CSVs into PostgreSQL

```powershell
py load_data.py
```

The loader imports sessions first, orders second, and events last. It refuses to load over non-empty tables unless you explicitly pass `--replace`. Only use `--replace` for the isolated synthetic Project 2 database; it replaces source rows.

### 5. Build staging views and marts

```powershell
py build_analytics.py
```

Expected objects:

- `project2.stg_sessions`
- `project2.stg_orders`
- `project2.stg_events`
- `project2.fct_verified_purchases`
- `project2.mart_campaign_performance`
- `project2.mart_daily_revenue`

`fct_verified_purchases` is deliberately a view: it returns one row per successful, receipt-backed business order. It is not a physical fact table. The business order is the revenue source of truth; event records are used for funnel metrics and reconciliation.

### 6. Run data quality checks

Connect to `project2_analytics` in pgAdmin/DBeaver and execute `sql/03_data_quality_checks.sql`. The orphan checks, invalid success-order checks, pending-terminal-field checks, and event/order mismatch checks should return zero. The status summary and verified revenue query return useful counts rather than zeroes.

### 7. Run Pandas reconciliation

```powershell
py analysis/analyze_data.py
```

The script writes campaign and daily revenue analysis into `analysis/output/`, compares independently aggregated Pandas metrics against the SQL mart, and exits with an assertion error if the numbers disagree beyond rounding tolerance.

### 8. Launch the dashboard

```powershell
py -m streamlit run app.py
```

Use the acquisition source selector to filter campaign results. The Revenue Health tab includes a date filter for daily verified revenue and order-state counts.

### 9. Run automated tests

```powershell
py -m pytest -q
```

## Metric definitions

See [`docs/metric_definitions.md`](docs/metric_definitions.md) for exact formulas and caveats. The key measures are:

- **Checkout-start rate:** distinct sessions with a `begin_checkout` event ÷ all distinct sessions.
- **Payment success rate:** distinct verified successful orders ÷ distinct payment attempts.
- **Verified revenue:** sum of amounts from successful orders with result code `0` and a non-null receipt.
- **AOV:** verified revenue ÷ distinct verified successful orders.

## Repository map

```text
generate_mock_data.py
load_data.py
build_analytics.py
app.py
sql/
  00_create_source_tables.sql
  01_build_staging_views.sql
  02_build_analytics_marts.sql
  03_data_quality_checks.sql
analysis/
  analyze_data.py
tests/
  test_generator.py
docs/
  data_dictionary.md
  metric_definitions.md
.github/workflows/ci.yml
```

## Limitations

- The dataset is synthetic and only illustrates plausible scenarios; its rates and amounts are not industry benchmarks.
- The generator simulates one order/payment attempt per originating session. A production integration may require a separate payment-attempt table, callback deduplication, and reconciliation of late callbacks.
- No credentials should be committed. `.env` is ignored; `.env.example` contains local-only defaults.
- This project intentionally excludes machine learning, BigQuery, dbt, Kafka, microservices, and A/B testing.
