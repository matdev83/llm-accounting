import logging
from datetime import datetime, timezone  # Import timezone
from typing import Dict, List, Optional, Tuple  # Optional was missing
from sqlalchemy import text
from sqlalchemy.engine import Connection  # For type hinting

from llm_accounting.backends.base import UsageEntry, UsageStats

logger = logging.getLogger(__name__)


def insert_usage_query(conn: Connection, entry: UsageEntry) -> None:
    """Insert a new usage entry into the database using named parameters."""
    # Ensure timestamp is naive UTC and formatted consistently
    formatted_timestamp: Optional[str] = None
    if entry.timestamp:
        # Convert to UTC, then make naive, then format
        utc_timestamp = entry.timestamp.astimezone(timezone.utc)  # Corrected
        naive_utc_timestamp = utc_timestamp.replace(tzinfo=None)
        # Use full microsecond precision for storage
        formatted_timestamp = naive_utc_timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')

    params = {
        "timestamp": formatted_timestamp,
        "model": entry.model,
        "prompt_tokens": entry.prompt_tokens,
        "completion_tokens": entry.completion_tokens,
        "total_tokens": entry.total_tokens,
        "local_prompt_tokens": entry.local_prompt_tokens,
        "local_completion_tokens": entry.local_completion_tokens,
        "local_total_tokens": entry.local_total_tokens,
        "cost": entry.cost,
        "execution_time": entry.execution_time,
        "caller_name": entry.caller_name,
        "username": entry.username,
        "cached_tokens": entry.cached_tokens,
        "reasoning_tokens": entry.reasoning_tokens,
        "project": entry.project,
    }
    logger.debug(f"Inserting usage with timestamp: {formatted_timestamp}")
    logger.debug(f"Insert parameters: {params}")

    sql = text("""
        INSERT INTO accounting_entries (
            timestamp, model, prompt_tokens, completion_tokens, total_tokens,
            local_prompt_tokens, local_completion_tokens, local_total_tokens,
            cost, execution_time, caller_name, username, cached_tokens, reasoning_tokens, project
        ) VALUES (
            :timestamp, :model, :prompt_tokens, :completion_tokens, :total_tokens,
            :local_prompt_tokens, :local_completion_tokens, :local_total_tokens,
            :cost, :execution_time, :caller_name, :username, :cached_tokens, :reasoning_tokens, :project
        )
    """)
    conn.execute(sql, params)
    # Removed conn.commit() - let the caller in SQLiteBackend handle transaction management.


def get_period_stats_query(
    conn: Connection, start: datetime, end: datetime
) -> UsageStats:
    """Get aggregated statistics for a time period from the database using named parameters."""
    sql = text("""
        SELECT
            SUM(prompt_tokens) as sum_prompt_tokens,
            SUM(completion_tokens) as sum_completion_tokens,
            SUM(total_tokens) as sum_total_tokens,
            SUM(local_prompt_tokens) as sum_local_prompt_tokens,
            SUM(local_completion_tokens) as sum_local_completion_tokens,
            SUM(local_total_tokens) as sum_local_total_tokens,
            SUM(cost) as sum_cost,
            SUM(execution_time) as sum_execution_time,
            AVG(prompt_tokens) as avg_prompt_tokens,
            AVG(completion_tokens) as avg_completion_tokens,
            AVG(total_tokens) as avg_total_tokens,
            AVG(local_prompt_tokens) as avg_local_prompt_tokens,
            AVG(local_completion_tokens) as avg_local_completion_tokens,
            AVG(local_total_tokens) as avg_local_total_tokens,
            AVG(cost) as avg_cost,
            AVG(execution_time) as avg_execution_time
        FROM accounting_entries
        WHERE timestamp BETWEEN :start_time AND :end_time
    """)

    # Ensure start and end times are naive UTC and formatted consistently for querying
    fmt = '%Y-%m-%d %H:%M:%S.%f'  # Use full microsecond precision
    start_naive_utc_str = start.astimezone(timezone.utc).replace(tzinfo=None).strftime(fmt)
    end_naive_utc_str = end.astimezone(timezone.utc).replace(tzinfo=None).strftime(fmt)

    result = conn.execute(sql, {"start_time": start_naive_utc_str, "end_time": end_naive_utc_str})
    row = result.fetchone()

    if not row or row.sum_cost is None:  # Check if any aggregation happened (e.g. sum_cost is a good indicator)
        # Return default UsageStats if no data
        return UsageStats()

    # Create a dictionary from the row, defaulting None values appropriately for UsageStats
    stats_data = {key: (value or 0) if isinstance(getattr(UsageStats, key, None), int) else (value or 0.0)
                  for key, value in row._mapping.items()}
    return UsageStats(**stats_data)


def get_model_stats_query(
    conn: Connection, start: datetime, end: datetime
) -> List[Tuple[str, UsageStats]]:
    """Get statistics grouped by model for a time period from the database using named parameters."""
    sql = text("""
        SELECT
            model,
            SUM(prompt_tokens) as sum_prompt_tokens,
            SUM(completion_tokens) as sum_completion_tokens,
            SUM(total_tokens) as sum_total_tokens,
            SUM(local_prompt_tokens) as sum_local_prompt_tokens,
            SUM(local_completion_tokens) as sum_local_completion_tokens,
            SUM(local_total_tokens) as sum_local_total_tokens,
            SUM(cost) as sum_cost,
            SUM(execution_time) as sum_execution_time,
            AVG(prompt_tokens) as avg_prompt_tokens,
            AVG(completion_tokens) as avg_completion_tokens,
            AVG(total_tokens) as avg_total_tokens,
            AVG(local_prompt_tokens) as avg_local_prompt_tokens,
            AVG(local_completion_tokens) as avg_local_completion_tokens,
            AVG(local_total_tokens) as avg_local_total_tokens,
            AVG(cost) as avg_cost,
            AVG(execution_time) as avg_execution_time
        FROM accounting_entries
        WHERE timestamp BETWEEN :start_time AND :end_time
        GROUP BY model
    """)

    # Ensure start and end times are naive UTC and formatted consistently for querying
    fmt = '%Y-%m-%d %H:%M:%S.%f'  # Use full microsecond precision
    start_naive_utc_str = start.astimezone(timezone.utc).replace(tzinfo=None).strftime(fmt)
    end_naive_utc_str = end.astimezone(timezone.utc).replace(tzinfo=None).strftime(fmt)

    result = conn.execute(sql, {"start_time": start_naive_utc_str, "end_time": end_naive_utc_str})
    rows = result.fetchall()

    model_stats = []
    for row in rows:
        stats_data = {key: (value or 0) if isinstance(getattr(UsageStats, key, None), int) else (value or 0.0)
                      for key, value in row._mapping.items() if key != 'model'}
        model_stats.append((str(row.model), UsageStats(**stats_data)))
    return model_stats


def get_model_rankings_query(
    conn: Connection, start: datetime, end: datetime
) -> Dict[str, List[Tuple[str, float]]]:
    """Get model rankings based on different metrics from the database using named parameters."""
    # Ensure start and end times are naive UTC and formatted consistently for querying
    fmt = '%Y-%m-%d %H:%M:%S.%f'  # Use full microsecond precision
    start_naive_utc_str = start.astimezone(timezone.utc).replace(tzinfo=None).strftime(fmt)
    end_naive_utc_str = end.astimezone(timezone.utc).replace(tzinfo=None).strftime(fmt)
    params = {"start_time": start_naive_utc_str, "end_time": end_naive_utc_str}

    prompt_tokens_sql = text("""
        SELECT model, SUM(prompt_tokens) as total
        FROM accounting_entries
        WHERE timestamp BETWEEN :start_time AND :end_time
        GROUP BY model
        ORDER BY total DESC
    """)
    result_prompt = conn.execute(prompt_tokens_sql, params)
    prompt_tokens_ranking = [(str(row.model), float(row.total or 0)) for row in result_prompt.fetchall()]

    cost_sql = text("""
        SELECT model, SUM(cost) as total
        FROM accounting_entries
        WHERE timestamp BETWEEN :start_time AND :end_time
        GROUP BY model
        ORDER BY total DESC
    """)
    result_cost = conn.execute(cost_sql, params)
    cost_ranking = [(str(row.model), float(row.total or 0.0)) for row in result_cost.fetchall()]

    return {"prompt_tokens": prompt_tokens_ranking, "cost": cost_ranking}


def tail_query(conn: Connection, n: int = 10) -> List[UsageEntry]:
    """Get the n most recent usage entries from the database using named parameters."""
    sql = text("""
        SELECT
            timestamp, model, prompt_tokens, completion_tokens, total_tokens,
            local_prompt_tokens, local_completion_tokens, local_total_tokens,
            cost, execution_time, caller_name, username, cached_tokens, reasoning_tokens, project
        FROM accounting_entries
        ORDER BY timestamp DESC, id DESC
        LIMIT :limit_n
    """)

    result = conn.execute(sql, {"limit_n": n})
    rows = result.fetchall()

    return [
        UsageEntry(
            model=row.model,
            prompt_tokens=row.prompt_tokens,
            completion_tokens=row.completion_tokens,
            total_tokens=row.total_tokens,
            local_prompt_tokens=row.local_prompt_tokens,
            local_completion_tokens=row.local_completion_tokens,
            local_total_tokens=row.local_total_tokens,
            cost=row.cost,
            execution_time=row.execution_time,
            timestamp=datetime.fromisoformat(row.timestamp),  # Ensure timestamp is datetime object
            caller_name=row.caller_name,
            username=row.username,
            cached_tokens=row.cached_tokens,
            reasoning_tokens=row.reasoning_tokens,
            project=row.project,
        )
        for row in rows
    ]
