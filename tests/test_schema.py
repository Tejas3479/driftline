import asyncio
import pytest
from sqlalchemy import inspect
from src.db.session import engine

def test_all_tables_exist_and_valid():
    async def _run_test():
        EXPECTED_TABLES = {
            "workspaces": ["id", "name", "created_at"],
            "users": ["id", "workspace_id", "email", "role"],
            "metrics": ["id", "workspace_id", "name", "unit", "direction_good", "sensitivity", "grain", "created_at"],
            "dimension_defs": ["id", "metric_id", "name"],
            "observations": ["id", "metric_id", "date", "dimension_values", "value"],
            "daily_rollups": ["id", "metric_id", "date", "value_total", "trend", "seasonal", "residual"],
            "anomalies": ["id", "metric_id", "date", "severity_score", "type", "z_score", "isolation_score", "status", "explanation_text", "created_at"],
            "anomaly_drivers": ["id", "anomaly_id", "dimension_name", "dimension_value", "contribution_value", "contribution_pct", "rank"],
            "forecasts": ["id", "metric_id", "forecast_date", "horizon_days", "p10", "p50", "p90", "model_version", "generated_at"],
            "forecast_accuracy_log": ["id", "metric_id", "date", "predicted_p50", "actual", "abs_pct_error"],
            "digests": ["id", "workspace_id", "period_start", "period_end", "pdf_path", "generated_at"],
            "alert_rules": ["id", "metric_id", "min_severity", "channels"],
        }

        async with engine.connect() as conn:
            def check_schema(sync_conn):
                inspector = inspect(sync_conn)
                existing_tables = inspector.get_table_names()
                
                for table_name, expected_cols in EXPECTED_TABLES.items():
                    assert table_name in existing_tables, f"Table '{table_name}' is missing from database schema."
                    
                    columns = [col["name"] for col in inspector.get_columns(table_name)]
                    for col in expected_cols:
                        assert col in columns, f"Column '{col}' missing from table '{table_name}'."
                
                # Check required composite indexes on (metric_id, date) / (metric_id, forecast_date)
                for table, expected_idx in [
                    ("observations", "ix_observations_metric_date"),
                    ("daily_rollups", "ix_daily_rollups_metric_date"),
                    ("anomalies", "ix_anomalies_metric_date"),
                    ("forecasts", "ix_forecasts_metric_date"),
                ]:
                    indexes = [idx["name"] for idx in inspector.get_indexes(table)]
                    assert expected_idx in indexes, f"Index '{expected_idx}' missing from table '{table}'."

            await conn.run_sync(check_schema)

    asyncio.run(_run_test())
