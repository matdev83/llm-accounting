import sys
from datetime import datetime, timedelta

from rich.table import Table

from llm_accounting import LLMAccounting

from ..utils import console, format_float, format_time, format_tokens


def run_stats(args, accounting: LLMAccounting):
    """Show usage statistics"""
    now = datetime.now()
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
            periods_to_process.append(("Custom", start_date, end_date))
        except ValueError:
            console.print("[red]Error: Invalid date format. Use YYYY-MM-DD.[/red]")
            sys.exit(1)

    if not periods_to_process:
        console.print(
            "Please specify a time period (--period daily|weekly|monthly|yearly) or custom range (--start and --end)"
        )
        sys.exit(1)

    for period_name, start, end in periods_to_process:
        console.print(
            f"\n[bold]=== {period_name} Stats ({start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')})[/bold]"
        )

        # Get overall stats
        stats = accounting.backend.get_period_stats(start, end)

        # Create table for overall stats
        table = Table(title="Overall Totals")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right", style="green")

        table.add_row("Prompt Tokens", format_tokens(stats.sum_prompt_tokens))
        table.add_row("Completion Tokens", format_tokens(stats.sum_completion_tokens))
        table.add_row("Total Tokens", format_tokens(stats.sum_total_tokens))
        table.add_row("Total Cost", f"${format_float(stats.sum_cost)}")
        table.add_row("Total Execution Time", format_time(stats.sum_execution_time))

        console.print(table)

        # Create table for averages
        table = Table(title="Averages")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right", style="green")

        table.add_row(
            "Prompt Tokens",
            format_tokens(
                int(stats.avg_prompt_tokens)
                if stats.avg_prompt_tokens is not None
                else 0
            ),
        )
        table.add_row(
            "Completion Tokens",
            format_tokens(
                int(stats.avg_completion_tokens)
                if stats.avg_completion_tokens is not None
                else 0
            ),
        )
        table.add_row(
            "Total Tokens",
            format_tokens(
                int(stats.avg_total_tokens) if stats.avg_total_tokens is not None else 0
            ),
        )
        table.add_row("Average Cost", f"${format_float(stats.avg_cost)}")
        table.add_row("Average Execution Time", format_time(stats.avg_execution_time))

        console.print(table)

        # Get model-specific stats
        model_stats = accounting.backend.get_model_stats(start, end)
        if model_stats:
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
                    format_tokens(
                        stats.sum_prompt_tokens
                        if stats.sum_prompt_tokens is not None
                        else 0
                    ),
                    format_tokens(
                        stats.sum_completion_tokens
                        if stats.sum_completion_tokens is not None
                        else 0
                    ),
                    format_tokens(
                        stats.sum_total_tokens
                        if stats.sum_total_tokens is not None
                        else 0
                    ),
                    f"${format_float(stats.sum_cost)}",
                    format_time(stats.sum_execution_time),
                )

            console.print(table)

        # Get rankings
        rankings = accounting.backend.get_model_rankings(start, end)
        for metric, models in rankings.items():
            if models:
                table = Table(title=f"Rankings by {metric.replace('_', ' ').title()}")
                table.add_column("Rank", style="cyan")
                table.add_column("Model", style="cyan")
                table.add_column("Total", justify="right", style="green")

                for i, (model, total) in enumerate(models, 1):
                    if metric in ["cost"]:
                        value = f"${format_float(total)}"
                    elif metric in ["execution_time"]:
                        value = format_time(total)
                    else:
                        value = format_tokens(int(total) if total is not None else 0)
                    table.add_row(str(i), model, value)

                console.print(table)
