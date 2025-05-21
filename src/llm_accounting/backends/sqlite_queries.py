import sqlite3
from datetime import datetime
from typing import Dict, List, Tuple

from llm_accounting.backends.base import UsageEntry, UsageStats


def insert_usage_query(conn: sqlite3.Connection, entry: UsageEntry) -> None:
    """Insert a new usage entry into the database."""
    # If timestamp is None, let SQLite use CURRENT_TIMESTAMP
    timestamp = entry.timestamp.isoformat() if entry.timestamp is not None else None

    conn.execute(
        """
        INSERT INTO accounting_entries (
            datetime,
            model,
            prompt_tokens,
            completion_tokens,
            total_tokens,
            local_prompt_tokens,
            local_completion_tokens,
            local_total_tokens,
            cost,
            execution_time,
            caller_name,
            username,
            cached_tokens,
            reasoning_tokens
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            timestamp,
            entry.model,
            entry.prompt_tokens,
            entry.completion_tokens,
            entry.total_tokens,
            entry.local_prompt_tokens,
            entry.local_completion_tokens,
            entry.local_total_tokens,
            entry.cost,
            entry.execution_time,
            entry.caller_name,
            entry.username,
            entry.cached_tokens,
            entry.reasoning_tokens,
        ),
    )
    conn.commit()


def get_period_stats_query(
    conn: sqlite3.Connection, start: datetime, end: datetime
) -> UsageStats:
    """Get aggregated statistics for a time period from the database."""
    cursor = conn.execute(
        """
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
        WHERE datetime BETWEEN ? AND ?
    """,
        (start.isoformat(), end.isoformat()),
    )
    row = cursor.fetchone()

    if not row:
        return UsageStats(
            sum_prompt_tokens=0,
            sum_completion_tokens=0,
            sum_total_tokens=0,
            sum_local_prompt_tokens=0,
            sum_local_completion_tokens=0,
            sum_local_total_tokens=0,
            sum_cost=0.0,
            sum_execution_time=0.0,
            avg_prompt_tokens=0.0,
            avg_completion_tokens=0.0,
            avg_total_tokens=0.0,
            avg_local_prompt_tokens=0.0,
            avg_local_completion_tokens=0.0,
            avg_local_total_tokens=0.0,
            avg_cost=0.0,
            avg_execution_time=0.0,
        )

    return UsageStats(
        sum_prompt_tokens=row[0] or 0,
        sum_completion_tokens=row[1] or 0,
        sum_total_tokens=row[2] or 0,
        sum_local_prompt_tokens=row[3] or 0,
        sum_local_completion_tokens=row[4] or 0,
        sum_local_total_tokens=row[5] or 0,
        sum_cost=row[6] or 0.0,
        sum_execution_time=row[7] or 0.0,
        avg_prompt_tokens=row[8] or 0.0,
        avg_completion_tokens=row[9] or 0.0,
        avg_total_tokens=row[10] or 0.0,
        avg_local_prompt_tokens=row[11] or 0.0,
        avg_local_completion_tokens=row[12] or 0.0,
        avg_local_total_tokens=row[13] or 0.0,
        avg_cost=row[14] or 0.0,
        avg_execution_time=row[15] or 0.0,
    )


def get_model_stats_query(
    conn: sqlite3.Connection, start: datetime, end: datetime
) -> List[Tuple[str, UsageStats]]:
    """Get statistics grouped by model for a time period from the database."""
    cursor = conn.execute(
        """
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
        WHERE datetime BETWEEN ? AND ?
        GROUP BY model
    """,
        (start.isoformat(), end.isoformat()),
    )
    rows = cursor.fetchall()

    return [
        (
            row[0],
            UsageStats(
                sum_prompt_tokens=row[1] or 0,
                sum_completion_tokens=row[2] or 0,
                sum_total_tokens=row[3] or 0,
                sum_local_prompt_tokens=row[4] or 0,
                sum_local_completion_tokens=row[5] or 0,
                sum_local_total_tokens=row[6] or 0,
                sum_cost=row[7] or 0.0,
                sum_execution_time=row[8] or 0.0,
                avg_prompt_tokens=row[9] or 0.0,
                avg_completion_tokens=row[10] or 0.0,
                avg_total_tokens=row[11] or 0.0,
                avg_local_prompt_tokens=row[12] or 0.0,
                avg_local_completion_tokens=row[13] or 0.0,
                avg_local_total_tokens=row[14] or 0.0,
                avg_cost=row[15] or 0.0,
                avg_execution_time=row[16] or 0.0,
            ),
        )
        for row in rows
    ]


def get_model_rankings_query(
    conn: sqlite3.Connection, start: datetime, end: datetime
) -> Dict[str, List[Tuple[str, float]]]:
    """Get model rankings based on different metrics from the database."""
    # Get prompt tokens ranking
    prompt_tokens_query = """
        SELECT model, SUM(prompt_tokens) as total
        FROM accounting_entries
        WHERE datetime BETWEEN ? AND ?
        GROUP BY model
        ORDER BY total DESC
    """
    cursor = conn.execute(prompt_tokens_query, (start.isoformat(), end.isoformat()))
    prompt_tokens_ranking = [(row[0], row[1]) for row in cursor.fetchall()]

    # Get cost ranking
    cost_query = """
        SELECT model, SUM(cost) as total
        FROM accounting_entries
        WHERE datetime BETWEEN ? AND ?
        GROUP BY model
        ORDER BY total DESC
    """
    cursor = conn.execute(cost_query, (start.isoformat(), end.isoformat()))
    cost_ranking = [(row[0], row[1]) for row in cursor.fetchall()]

    return {"prompt_tokens": prompt_tokens_ranking, "cost": cost_ranking}


def tail_query(conn: sqlite3.Connection, n: int = 10) -> List[UsageEntry]:
    """Get the n most recent usage entries from the database."""
    cursor = conn.execute(
        """
        SELECT
            datetime,
            model,
            prompt_tokens,
            completion_tokens,
            total_tokens,
            local_prompt_tokens,
            local_completion_tokens,
            local_total_tokens,
            cost,
            execution_time,
            caller_name,
            username,
            cached_tokens,
            reasoning_tokens
        FROM accounting_entries
        ORDER BY datetime DESC
        LIMIT ?
    """,
        (n,),
    )
    rows = cursor.fetchall()

    return [
        UsageEntry(
            model=row[1],
            prompt_tokens=row[2],
            completion_tokens=row[3],
            total_tokens=row[4],
            local_prompt_tokens=row[5],
            local_completion_tokens=row[6],
            local_total_tokens=row[7],
            cost=row[8],
            execution_time=row[9],
            timestamp=datetime.fromisoformat(row[0]),
            caller_name=row[10],
            username=row[11],
            cached_tokens=row[12],
            reasoning_tokens=row[13],
        )
        for row in rows
    ]
