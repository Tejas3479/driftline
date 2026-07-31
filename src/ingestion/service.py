import asyncio
import io
import json
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Set
import pandas as pd
import polars as pl
from sqlalchemy import select, delete, text, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Workspace
from src.ingestion.models import Metric, DimensionDef, Observation, DirectionGoodEnum, GrainEnum
from src.ingestion.schemas import MetricCreateSchema, DataConfirmSchema

DATE_FORMATS = [
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%Y/%m/%d",
    "%d-%m-%Y",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
]

def parse_date_str(val: Any) -> Optional[date]:
    """Helper to parse date string across multiple formats."""
    if val is None:
        return None
    if isinstance(val, (date, datetime)):
        return val.date() if isinstance(val, datetime) else val
    val_str = str(val).strip()
    if not val_str:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(val_str, fmt).date()
        except ValueError:
            continue
    return None

def is_numeric(val: Any) -> bool:
    """Helper to check if a value is numeric."""
    if val is None or val == "":
        return False
    try:
        float(val)
        return True
    except (ValueError, TypeError):
        return False

async def seed_default_workspace(db: AsyncSession) -> Workspace:
    """
    Atomically seeds default Workspace (ID #1) if missing using ON CONFLICT DO NOTHING,
    and updates PostgreSQL sequence to prevent auto-increment ID collisions.
    """
    await db.execute(
        text(
            "INSERT INTO workspaces (id, name, created_at) "
            "VALUES (1, 'Default Workspace', NOW()) "
            "ON CONFLICT (id) DO NOTHING;"
        )
    )
    await db.execute(
        text(
            "SELECT setval('workspaces_id_seq', (SELECT GREATEST(MAX(id), 1) FROM workspaces));"
        )
    )
    await db.commit()
    res = await db.execute(select(Workspace).where(Workspace.id == 1))
    return res.scalar_one()

async def ensure_workspace_exists(db: AsyncSession, workspace_id: int = 1) -> Workspace:
    """Ensure workspace with given ID exists, creating default if missing."""
    if workspace_id == 1:
        return await seed_default_workspace(db)
    result = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalar_one_or_none()
    if not workspace:
        workspace = Workspace(id=workspace_id, name=f"Workspace #{workspace_id}")
        db.add(workspace)
        await db.commit()
        await db.refresh(workspace)
    return workspace

async def create_metric(db: AsyncSession, schema: MetricCreateSchema, current_workspace_id: int) -> Metric:
    """Create a new metric configuration."""
    ws_id = current_workspace_id
    await ensure_workspace_exists(db, ws_id)
    metric = Metric(
        workspace_id=ws_id,
        name=schema.name,
        unit=schema.unit,
        direction_good=schema.direction_good,
        sensitivity=schema.sensitivity,
        grain=schema.grain,
    )
    db.add(metric)
    await db.commit()
    await db.refresh(metric)
    return metric

async def get_metric(db: AsyncSession, metric_id: int) -> Optional[Metric]:
    """Retrieve metric by ID."""
    result = await db.execute(select(Metric).where(Metric.id == metric_id))
    return result.scalar_one_or_none()

async def update_metric(db: AsyncSession, metric: Metric, schema: 'MetricUpdateSchema') -> Metric:
    """Update metric configuration."""
    if schema.sensitivity is not None:
        metric.sensitivity = schema.sensitivity
    if schema.direction_good is not None:
        metric.direction_good = schema.direction_good
    if schema.z_score_weight is not None:
        metric.z_score_weight = schema.z_score_weight
    
    await db.commit()
    await db.refresh(metric)
    return metric

def inspect_and_validate_csv(metric: Metric, file_bytes: bytes) -> Dict[str, Any]:
    """
    Step 2: Read CSV with Polars, infer columns, generate validation report, and detect date gaps.
    """
    # Read file content using Polars
    try:
        df = pl.read_csv(io.BytesIO(file_bytes), infer_schema_length=1000)
    except Exception as e:
        return {
            "inferred_mapping": {"date_col": "", "value_col": "", "dimension_cols": []},
            "validation_report": {
                "is_valid": False,
                "total_rows": 0,
                "errors": [{"row_number": 0, "column": "file", "issue": f"Invalid CSV file format: {str(e)}", "invalid_value": None}],
                "date_gaps": [],
                "inferred_mapping": {"date_col": "", "value_col": "", "dimension_cols": []}
            },
            "rows": []
        }

    columns = df.columns
    total_rows = df.height

    if total_rows == 0:
        return {
            "inferred_mapping": {"date_col": "", "value_col": "", "dimension_cols": []},
            "validation_report": {
                "is_valid": False,
                "total_rows": 0,
                "errors": [{"row_number": 0, "column": "file", "issue": "CSV file is empty", "invalid_value": None}],
                "date_gaps": [],
                "inferred_mapping": {"date_col": "", "value_col": "", "dimension_cols": []}
            },
            "rows": []
        }

    # Step 2.b: Infer columns
    best_date_col = ""
    best_date_rate = 0.0

    for col in columns:
        col_vals = df[col].to_list()
        valid_date_count = sum(1 for v in col_vals if parse_date_str(v) is not None)
        rate = valid_date_count / total_rows
        if rate > 0.9 and rate > best_date_rate:
            best_date_rate = rate
            best_date_col = col

    # Fallback to column named 'date' or 'day' or first column if none >90%
    if not best_date_col:
        for col in columns:
            if col.lower() in ["date", "day", "timestamp"]:
                best_date_col = col
                break
        if not best_date_col and len(columns) > 0:
            best_date_col = columns[0]

    # Infer value column (most populated numeric column non-date)
    best_value_col = ""
    best_numeric_count = -1

    for col in columns:
        if col == best_date_col:
            continue
        col_vals = df[col].to_list()
        num_count = sum(1 for v in col_vals if is_numeric(v))
        if num_count > best_numeric_count:
            best_numeric_count = num_count
            best_value_col = col

    # Up to 3 remaining candidate dimension columns
    candidate_dim_cols = [
        col for col in columns
        if col not in (best_date_col, best_value_col)
    ][:3]

    inferred_mapping = {
        "date_col": best_date_col,
        "value_col": best_value_col,
        "dimension_cols": candidate_dim_cols
    }

    # Step 2.c: Generate validation report
    errors = []
    seen_combos: Dict[Tuple[str, str], int] = {}
    valid_dates: Set[date] = set()

    for idx in range(total_rows):
        row_num = idx + 2  # 1-indexed file line (Line 1 is header, Line 2 is first data row)
        row_dict = {col: df[col][idx] for col in columns}

        # 1. Missing / unparseable date
        raw_date_val = row_dict.get(best_date_col)
        parsed_d = parse_date_str(raw_date_val)
        if parsed_d is None:
            errors.append({
                "row_number": row_num,
                "column": best_date_col,
                "issue": "Missing or unparseable date",
                "invalid_value": str(raw_date_val) if raw_date_val is not None else None
            })
        else:
            valid_dates.add(parsed_d)

        # 2. Non-numeric value
        raw_num_val = row_dict.get(best_value_col)
        if not is_numeric(raw_num_val):
            errors.append({
                "row_number": row_num,
                "column": best_value_col,
                "issue": "Non-numeric value in value column",
                "invalid_value": str(raw_num_val) if raw_num_val is not None else None
            })
        else:
            num_float = float(raw_num_val)
            # 3. Disallowed negative values check
            if metric.direction_good == DirectionGoodEnum.up_is_good and num_float < 0:
                errors.append({
                    "row_number": row_num,
                    "column": best_value_col,
                    "issue": f"Negative value '{num_float}' not allowed for metric '{metric.name}'",
                    "invalid_value": str(raw_num_val)
                })

        # 4. Duplicate (date, dimension_values) combinations
        if parsed_d is not None:
            dim_tuple = tuple(sorted((d_col, str(row_dict.get(d_col, "")).strip()) for d_col in candidate_dim_cols))
            combo_key = (parsed_d.isoformat(), json.dumps(dim_tuple))
            if combo_key in seen_combos:
                first_row = seen_combos[combo_key]
                errors.append({
                    "row_number": row_num,
                    "column": best_date_col,
                    "issue": f"Duplicate (date, dimensions) combination (matches row {first_row})",
                    "invalid_value": f"{parsed_d.isoformat()} - {dict(dim_tuple)}"
                })
            else:
                seen_combos[combo_key] = row_num

    # Step 2.d: Detect date gaps
    date_gaps = []
    if valid_dates:
        min_d = min(valid_dates)
        max_d = max(valid_dates)
        
        step_days = 7 if metric.grain == GrainEnum.weekly else 1
        current = min_d
        missing_dates = []
        
        while current <= max_d:
            if current not in valid_dates:
                missing_dates.append(current.isoformat())
            current += timedelta(days=step_days)
            
        if missing_dates:
            date_gaps = missing_dates

    is_valid = len(errors) == 0

    # Format rows preview for caller
    rows_preview = []
    for idx in range(total_rows):
        rows_preview.append({col: (str(df[col][idx]) if df[col][idx] is not None else None) for col in columns})

    validation_report = {
        "is_valid": is_valid,
        "total_rows": total_rows,
        "errors": errors,
        "date_gaps": date_gaps,
        "inferred_mapping": inferred_mapping
    }

    return {
        "inferred_mapping": inferred_mapping,
        "validation_report": validation_report,
        "rows": rows_preview
    }

async def confirm_and_persist_observations(
    db: AsyncSession,
    metric_id: int,
    schema: DataConfirmSchema
) -> Dict[str, Any]:
    """
    Step 3 & 4: Convert Polars -> Pandas right before DB insert.
    Handle append (diff) vs replace.
    Persist dimension_defs and observations.
    """
    metric = await get_metric(db, metric_id)
    if not metric:
        raise ValueError(f"Metric with id {metric_id} does not exist.")

    # 1. Update dimension_defs table for new dimensions
    if schema.dimension_cols:
        existing_dims_res = await db.execute(
            select(DimensionDef.name).where(DimensionDef.metric_id == metric_id)
        )
        existing_dim_names = set(existing_dims_res.scalars().all())

        for dim_name in schema.dimension_cols:
            if dim_name not in existing_dim_names:
                db.add(DimensionDef(metric_id=metric_id, name=dim_name))
                existing_dim_names.add(dim_name)
        await db.flush()

    # 2. Process incoming rows to standard dictionaries (offloaded from event loop)
    def _process_incoming():
        _pl_df = pl.DataFrame(schema.rows)
        _pd_df = pd.DataFrame(_pl_df.to_dicts())
        processed = []
        for _, row in _pd_df.iterrows():
            d_val = parse_date_str(row.get(schema.date_col))
            if d_val is None:
                continue
            val = float(row.get(schema.value_col))
            dim_vals = {col: str(row.get(col, "")).strip() for col in schema.dimension_cols if col in row}
            processed.append({"date": d_val, "value": val, "dimension_values": dim_vals})
        return processed

    incoming_rows = await asyncio.to_thread(_process_incoming)

    inserted_count = 0
    updated_count = 0

    if schema.replace:
        # Delete existing observations for this metric
        await db.execute(delete(Observation).where(Observation.metric_id == metric_id))
        await db.flush()

        new_obs_list = []
        for row in incoming_rows:
            new_obs_list.append(Observation(
                metric_id=metric_id,
                date=row["date"],
                dimension_values=row["dimension_values"],
                value=row["value"]
            ))
        db.add_all(new_obs_list)
        inserted_count = len(new_obs_list)
    else:
        # Append / Diff mode
        existing_obs_res = await db.execute(
            select(Observation).where(Observation.metric_id == metric_id)
        )
        existing_obs_list = existing_obs_res.scalars().all()

        # Key existing obs by (date, json_serialized_sorted_dims)
        def make_key(d: date, dims: Dict[str, Any]) -> str:
            sorted_dims = sorted((k, str(v).strip()) for k, v in dims.items())
            return f"{d.isoformat()}::{json.dumps(sorted_dims)}"

        existing_lookup = {make_key(obs.date, obs.dimension_values): obs for obs in existing_obs_list}

        for row in incoming_rows:
            d_val = row["date"]
            val = row["value"]
            dim_vals = row["dimension_values"]

            key = make_key(d_val, dim_vals)
            if key in existing_lookup:
                existing_obs = existing_lookup[key]
                if existing_obs.value != val:
                    existing_obs.value = val
                    updated_count += 1
            else:
                new_obs = Observation(
                    metric_id=metric_id,
                    date=d_val,
                    dimension_values=dim_vals,
                    value=val
                )
                db.add(new_obs)
                existing_lookup[key] = new_obs
                inserted_count += 1

    await db.commit()

    # Trigger daily rollup and decomposition calculation
    from src.anomalies.service import run_daily_rollup_and_decomposition
    await run_daily_rollup_and_decomposition(db, metric_id)

    # Get total count via SQL aggregate
    total_obs_res = await db.execute(
        select(func.count()).select_from(Observation).where(Observation.metric_id == metric_id)
    )
    total_obs = total_obs_res.scalar_one()

    return {
        "metric_id": metric_id,
        "inserted_count": inserted_count,
        "updated_count": updated_count,
        "total_observations": total_obs
    }

async def list_metrics(db: AsyncSession, workspace_id: int) -> List[Metric]:
    """
    Retrieve all metric configurations for a given workspace.
    """
    result = await db.execute(select(Metric).where(Metric.workspace_id == workspace_id).order_by(Metric.id))
    return list(result.scalars().all())

async def delete_metric(db: AsyncSession, metric: Metric) -> None:
    """
    Delete a metric configuration and all related cascading data.
    """
    await db.delete(metric)
    await db.commit()
