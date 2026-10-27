"""Build staging views and analytical marts in the configured Project 2 database."""
from __future__ import annotations

from load_data import ROOT, get_engine, load_sql_file


def main() -> None:
    engine = get_engine()
    try:
        with engine.begin() as conn:
            load_sql_file(conn, ROOT / "sql" / "00_create_source_tables.sql")
            load_sql_file(conn, ROOT / "sql" / "01_build_staging_views.sql")
            load_sql_file(conn, ROOT / "sql" / "02_build_analytics_marts.sql")
            counts = conn.exec_driver_sql("""
                SELECT 'stg_sessions' AS object_name, COUNT(*) AS rows FROM project2.stg_sessions
                UNION ALL SELECT 'stg_orders', COUNT(*) FROM project2.stg_orders
                UNION ALL SELECT 'stg_events', COUNT(*) FROM project2.stg_events
                UNION ALL SELECT 'fct_verified_purchases', COUNT(*) FROM project2.fct_verified_purchases
                UNION ALL SELECT 'mart_campaign_performance', COUNT(*) FROM project2.mart_campaign_performance
            """).fetchall()
        print("Staging views and analytical marts built successfully:")
        for object_name, row_count in counts:
            print(f"  {object_name}: {row_count:,} rows")
    finally:
        engine.dispose()

if __name__ == "__main__":
    main()
