from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_sql(name):
    return (ROOT / "sql" / name).read_text(encoding="utf-8").lower()


def test_staging_views_use_source_schema_column_names():
    sql = read_sql("01_build_staging_views.sql")
    assert "from project2.analytics_sessions" in sql
    assert "from project2.orders" in sql
    assert "from project2.analytics_events" in sql
    assert "properties ->> 'failure_reason'" in sql
    assert "event_properties" not in sql


def test_verified_purchase_view_requires_success_code_and_receipt():
    sql = read_sql("02_build_analytics_marts.sql")
    assert "create or replace view project2.fct_verified_purchases" in sql
    assert "o.status = 'success'" in sql
    assert "o.result_code = '0'" in sql
    assert "o.mpesa_receipt_number is not null" in sql


def test_compose_is_separate_from_project_one_defaults():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8").lower()
    assert "project2-postgres" in compose
    assert "project2_postgres_data" in compose
    assert "${host_db_port:-5433}:5432" in compose
    assert "project_1-db-1" not in compose
