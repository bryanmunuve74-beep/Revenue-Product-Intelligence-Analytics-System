"""Load generated CSVs into the separate Project 2 PostgreSQL schema."""
from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = ROOT / "data"
DEFAULT_DATABASE_URL = "postgresql+pg8000://p2_user:p2_dev_only_password@localhost:5433/project2_analytics"


def get_engine() -> Engine:
    load_dotenv(ROOT / ".env")
    url = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    return create_engine(url, pool_pre_ping=True)


def read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Could not find {path}. Generate data first with generate_mock_data.py.")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return rows


def nullable(value: Any) -> Any:
    return None if value is None or value == "" else value


def load_sql_file(connection, path: Path) -> None:
    """Execute this project's simple DDL script one semicolon-delimited statement at a time."""
    script = path.read_text(encoding="utf-8")
    # This project's SQL files do not contain semicolons inside string literals or procedures.
    for statement in script.split(";"):
        statement = statement.strip()
        if statement:
            connection.exec_driver_sql(statement)


def chunks(rows: list[dict[str, Any]], size: int = 1000):
    for offset in range(0, len(rows), size):
        yield rows[offset:offset + size]


def main() -> None:
    parser = argparse.ArgumentParser(description="Load Project 2 synthetic CSVs into PostgreSQL.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--replace", action="store_true", help="Replace rows in the three source tables. Use only in the isolated Project 2 database.")
    args = parser.parse_args()

    sessions = read_csv(args.data_dir / "analytics_sessions.csv")
    orders = read_csv(args.data_dir / "orders.csv")
    events = read_csv(args.data_dir / "analytics_events.csv")
    engine = get_engine()

    session_insert = text("""
        INSERT INTO project2.analytics_sessions
        (session_id, started_at, utm_source, utm_medium, utm_campaign, landing_page, referrer, device_category, data_origin, ga_client_id)
        VALUES (:session_id, :started_at, :utm_source, :utm_medium, :utm_campaign, :landing_page, :referrer, :device_category, :data_origin, :ga_client_id)
    """)
    order_insert = text("""
        INSERT INTO project2.orders
        (id, session_id, phone_number, amount, status, checkout_request_id, merchant_request_id, result_code, result_desc, mpesa_receipt_number, created_at, updated_at)
        VALUES (:id, :session_id, :phone_number, :amount, :status, :checkout_request_id, :merchant_request_id, :result_code, :result_desc, :mpesa_receipt_number, :created_at, :updated_at)
    """)
    event_insert = text("""
        INSERT INTO project2.analytics_events
        (event_id, session_id, event_name, order_id, occurred_at, event_source, properties)
        VALUES (:event_id, :session_id, :event_name, :order_id, :occurred_at, :event_source, CAST(:properties AS JSONB))
    """)

    try:
        with engine.begin() as conn:
            load_sql_file(conn, ROOT / "sql" / "00_create_source_tables.sql")
            counts = {
                table: conn.execute(text(f"SELECT COUNT(*) FROM project2.{table}")).scalar_one()
                for table in ("analytics_sessions", "orders", "analytics_events")
            }
            if any(counts.values()) and not args.replace:
                raise RuntimeError(
                    "At least one source table already contains rows. Re-run with --replace only if you intend to replace the synthetic Project 2 data."
                )
            if args.replace:
                conn.exec_driver_sql(
                    "TRUNCATE TABLE project2.analytics_events, project2.orders, project2.analytics_sessions"
                )

            for batch in chunks(sessions):
                prepared = [{k: nullable(v) for k, v in row.items()} for row in batch]
                conn.execute(session_insert, prepared)
            for batch in chunks(orders):
                prepared = []
                for row in batch:
                    item = {k: nullable(v) for k, v in row.items()}
                    item["id"] = int(item["id"])
                    item["amount"] = item["amount"]
                    prepared.append(item)
                conn.execute(order_insert, prepared)
            for batch in chunks(events):
                prepared = []
                for row in batch:
                    item = {k: nullable(v) for k, v in row.items()}
                    item["event_id"] = int(item["event_id"])
                    item["order_id"] = int(item["order_id"]) if item["order_id"] else None
                    prepared.append(item)
                conn.execute(event_insert, prepared)

            actual = {
                table: conn.execute(text(f"SELECT COUNT(*) FROM project2.{table}")).scalar_one()
                for table in ("analytics_sessions", "orders", "analytics_events")
            }
            if actual != {
                "analytics_sessions": len(sessions),
                "orders": len(orders),
                "analytics_events": len(events),
            }:
                raise RuntimeError(f"Row-count verification failed: {actual}")
            orphan_orders = conn.execute(text("""
                SELECT COUNT(*) FROM project2.orders o
                LEFT JOIN project2.analytics_sessions s USING (session_id)
                WHERE s.session_id IS NULL
            """)).scalar_one()
            orphan_events = conn.execute(text("""
                SELECT COUNT(*) FROM project2.analytics_events e
                LEFT JOIN project2.analytics_sessions s USING (session_id)
                WHERE s.session_id IS NULL
            """)).scalar_one()
            missing_event_orders = conn.execute(text("""
                SELECT COUNT(*) FROM project2.analytics_events e
                LEFT JOIN project2.orders o ON o.id = e.order_id
                WHERE e.order_id IS NOT NULL AND o.id IS NULL
            """)).scalar_one()
            if orphan_orders or orphan_events or missing_event_orders:
                raise RuntimeError("Referential-integrity verification failed.")
    finally:
        engine.dispose()

    print("Load succeeded and row-count / relationship checks passed:")
    print(f"  analytics_sessions: {len(sessions):,}")
    print(f"  orders:             {len(orders):,}")
    print(f"  analytics_events:   {len(events):,}")
    print("Next: execute sql/01_build_staging_views.sql and sql/02_build_analytics_marts.sql.")

if __name__ == "__main__":
    main()
