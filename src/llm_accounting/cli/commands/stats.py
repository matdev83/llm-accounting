import sys
from datetime import datetime, timedelta
from typing import List, Tuple, Any  # Added for type hints

from rich.table import Table

from llm_accounting import LLMAccounting
from llm_accounting.backends.base import UsageStats  # Added for type hints

from ..utils import console, format_float, format_time, format_tokens


# --- START NEW HELPER FUNCTIONS ---


def _determine_periods_to_process(args, now: datetime) -> List[Tuple[str, datetime, datetime]]:
    periods_to_process = []
    if args.period:
        if args.period == "daily":
            start_date = datetime(now.year, now.month, now.day)
            periods_to_process.append(("Daily", start_date, now))
        elif args.period == "weekly":
            start_date = now - timedelta(days=now.weekday())
            start_date = datetime(start_date.year, start_date.month, start_date.day)
            periods_to_process.append(("Weekly", start_date, now))
        elif args.period == "monthly":
            start_date = datetime(now.year, now.month, 1)
            periods_to_process.append(("Monthly", start_date, now))
        elif args.period == "yearly":
            start_date = datetime(now.year, 1, 1)
            periods_to_process.append(("Yearly", start_date, now))
    elif args.start and args.end:
        try:
            start_date = datetime.strptime(args.start, "%Y-%m-%d")
            end_date = datetime.strptime(args.end, "%Y-%m-%d")
            # Ensure end_date includes the whole day if it's just a date
            end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
            periods_to_process.append(("Custom", start_date, end_date))
        except ValueError:
            console.print("[red]Error: Invalid date format. Use YYYY-MM-DD.[/red]")
            sys.exit(1)

    if not periods_to_process:
        console.print(
            "Please specify a time period (--period daily|weekly|monthly|yearly) or custom range (--start and --end)"
        )
        sys.exit(1)
    return periods_to_process


def _display_overall_totals_table(stats: UsageStats) -> None:
    table = Table(title="Overall Totals")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="green")

    table.add_row("Prompt Tokens", format_tokens(stats.sum_prompt_tokens))
    table.add_row("Completion Tokens", format_tokens(stats.sum_completion_tokens))
    table.add_row("Total Tokens", format_tokens(stats.sum_total_tokens))
    table.add_row("Total Cost", f"${format_float(stats.sum_cost)}")
    table.add_row("Total Execution Time", format_time(stats.sum_execution_time))
    console.print(table)


def _display_averages_table(stats: UsageStats) -> None:
    table = Table(title="Averages")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="green")

    table.add_row(
        "Prompt Tokens",
        format_tokens(int(stats.avg_prompt_tokens) if stats.avg_prompt_tokens is not None else 0)
    )
    table.add_row(
        "Completion Tokens",
        format_tokens(int(stats.avg_completion_tokens) if stats.avg_completion_tokens is not None else 0)
    )
    table.add_row(
        "Total Tokens",
        format_tokens(int(stats.avg_total_tokens) if stats.avg_total_tokens is not None else 0)
    )
    table.add_row("Average Cost", f"${format_float(stats.avg_cost)}")
    table.add_row("Average Execution Time", format_time(stats.avg_execution_time))
    console.print(table)


def _display_model_breakdown_table(model_stats: List[Tuple[str, UsageStats]]) -> None:
    if not model_stats:
        return

    table = Table(title="Model Breakdown")
    table.add_column("Model", style="cyan")
    table.add_column("Prompt Tokens", justify="right", style="green")
    table.add_column("Completion Tokens", justify="right", style="green")
    table.add_column("Total Tokens", justify="right", style="green")
    table.add_column("Cost", justify="right", style="green")
    table.add_column("Execution Time", justify="right", style="green")

    for model, stats in model_stats:
        table.add_row(
            model,
            format_tokens(stats.sum_prompt_tokens if stats.sum_prompt_tokens is not None else 0),
            format_tokens(stats.sum_completion_tokens if stats.sum_completion_tokens is not None else 0),
            format_tokens(stats.sum_total_tokens if stats.sum_total_tokens is not None else 0),
            f"${format_float(stats.sum_cost)}",
            format_time(stats.sum_execution_time),
        )
    console.print(table)


def _display_rankings_table(metric: str, models_data: List[Tuple[str, Any]]) -> None:
    if not models_data:
        return

    table = Table(title=f"Rankings by {metric.replace('_', ' ').title()}")
    table.add_column("Rank", style="cyan")
    table.add_column("Model", style="cyan")
    table.add_column("Total", justify="right", style="green")

    for i, (model, total) in enumerate(models_data, 1):
        # Assuming metric keys from backend are like 'cost', 'execution_time', 'prompt_tokens' etc.
        if "cost" in metric.lower():  # Make check more robust
            value = f"${format_float(total)}"
        elif "execution_time" in metric.lower():
            value = format_time(total)
        else:  # Default to token formatting for other metrics like prompt_tokens, completion_tokens, total_tokens
            value = format_tokens(int(total) if total is not None else 0)
        table.add_row(str(i), model, value)
    console.print(table)

# --- END NEW HELPER FUNCTIONS ---


def run_stats(args, accounting: LLMAccounting):
    """Show usage statistics"""
    now = datetime.now()
    periods_to_process = _determine_periods_to_process(args, now)

    for period_name, start, end in periods_to_process:
        console.print(
            f"\n[bold]=== {period_name} Stats ({start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')})[/bold]"
        )

        stats = accounting.backend.get_period_stats(start, end)
        _display_overall_totals_table(stats)
        _display_averages_table(stats)

        model_stats = accounting.backend.get_model_stats(start, end)
        _display_model_breakdown_table(model_stats)

        rankings = accounting.backend.get_model_rankings(start, end)
        for metric, models_data in rankings.items():
            _display_rankings_table(metric, models_data)
