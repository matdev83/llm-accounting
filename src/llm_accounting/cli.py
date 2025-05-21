import click
from datetime import datetime, timedelta
from rich.console import Console
from rich.table import Table
from rich.prompt import Confirm
import sys

from . import LLMAccounting
from .backends.sqlite import SQLiteBackend

console = Console()

def format_float(value: float) -> str:
    """Format float values for display"""
    return f"{value:.4f}" if value else "0.0000"

def format_time(value: float) -> str:
    """Format time values for display"""
    return f"{value:.2f}s" if value else "0.00s"

def format_tokens(value: int) -> str:
    """Format token counts for display"""
    return f"{value:,}" if value else "0"

def with_accounting(f):
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        accounting = None
        try:
            accounting = get_accounting(db_file=ctx.obj.get('db_file'))
            with accounting: # Use the context manager here
                return f(ctx, accounting, *args, **kwargs)
        except (ValueError, PermissionError, OSError, RuntimeError) as e:
            # print(f"Caught handled error: {type(e).__name__}: {e}") # For debugging
            console.print(f"[red]Error: {e}[/red]")
            ctx.exit(1)
        except SystemExit: # Allow SystemExit to pass through (e.g., from ctx.exit)
            raise
        except Exception as e:
            # print(f"Caught unexpected error: {type(e).__name__}: {e}") # For debugging
            # import traceback # For debugging
            # traceback.print_exc() # For debugging
            console.print(f"[red]Unexpected error: {e}[/red]")
            ctx.exit(2)
    return wrapper

@click.group(invoke_without_command=True)
@click.option('--db-file', type=click.Path(),
              help='SQLite database file path (must end with .sqlite, .sqlite3 or .db)')
@click.pass_context
def cli(ctx, db_file):
    """LLM Accounting CLI - Track and analyze LLM usage"""
    ctx.ensure_object(dict)
    ctx.obj['db_file'] = db_file

    # If no subcommand is given, print help
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())

def get_accounting(db_file=None):
    """Get an LLMAccounting instance with SQLite backend"""
    backend = SQLiteBackend(db_path=db_file)
    acc = LLMAccounting(backend=backend)
    # The context manager will handle __enter__ and __exit__
    return acc


@cli.command()
@click.option('--period', type=click.Choice(['daily', 'weekly', 'monthly', 'yearly']),
              help='Show stats for a specific period (daily, weekly, monthly, or yearly)')
@click.option('--start', type=click.DateTime(), help='Start date for custom period')
@click.option('--end', type=click.DateTime(), help='End date for custom period')
@with_accounting
def stats(ctx, accounting: LLMAccounting, period: str, start: datetime, end: datetime):
    """Show usage statistics"""
    now = datetime.now()
    periods_to_process = []

    if period:
        if period == 'daily':
            start_date = datetime(now.year, now.month, now.day)
            periods_to_process.append(("Daily", start_date, now))
        elif period == 'weekly':
            start_date = now - timedelta(days=now.weekday())
            start_date = datetime(start_date.year, start_date.month, start_date.day)
            periods_to_process.append(("Weekly", start_date, now))
        elif period == 'monthly':
            start_date = datetime(now.year, now.month, 1)
            periods_to_process.append(("Monthly", start_date, now))
        elif period == 'yearly':
            start_date = datetime(now.year, 1, 1)
            periods_to_process.append(("Yearly", start_date, now))
    elif start and end:
        periods_to_process.append(("Custom", start, end))

    if not periods_to_process:
        click.echo("Please specify a time period (--period daily|weekly|monthly|yearly) or custom range (--start and --end)")
        ctx.exit(1)

    for period_name, start, end in periods_to_process:
        console.print(f"\n[bold]=== {period_name} Stats ({start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')})[/bold]")

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

        table.add_row("Prompt Tokens", format_tokens(int(stats.avg_prompt_tokens) if stats.avg_prompt_tokens is not None else 0))
        table.add_row("Completion Tokens", format_tokens(int(stats.avg_completion_tokens) if stats.avg_completion_tokens is not None else 0))
        table.add_row("Total Tokens", format_tokens(int(stats.avg_total_tokens) if stats.avg_total_tokens is not None else 0))
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
                    format_tokens(stats.sum_prompt_tokens if stats.sum_prompt_tokens is not None else 0),
                    format_tokens(stats.sum_completion_tokens if stats.sum_completion_tokens is not None else 0),
                    format_tokens(stats.sum_total_tokens if stats.sum_total_tokens is not None else 0),
                    f"${format_float(stats.sum_cost)}",
                    format_time(stats.sum_execution_time)
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
                    if metric in ['cost']:
                        value = f"${format_float(total)}"
                    elif metric in ['execution_time']:
                        value = format_time(total)
                    else:
                        value = format_tokens(int(total) if total is not None else 0)
                    table.add_row(str(i), model, value)

                console.print(table)


@cli.command()
@click.option('-y', '--yes', is_flag=True, help='Skip confirmation prompt')
@with_accounting
def purge(ctx, accounting: LLMAccounting, yes):
    """Delete all usage entries from the database"""
    if not yes:
        if not Confirm.ask("Are you sure you want to delete all usage entries? This action cannot be undone."):
            console.print("[yellow]Purge operation cancelled[/yellow]")
            return

    accounting.purge()
    console.print("[green]All usage entries have been deleted[/green]")


@cli.command()
@click.option('-n', '--number', type=int, default=10, help='Number of recent entries to show')
@with_accounting
def tail(ctx, accounting: LLMAccounting, number):
    """Show the most recent usage entries"""
    entries = accounting.tail(number)

    if not entries:
        console.print("[yellow]No usage entries found[/yellow]")
        return

    # Create table for entries
    table = Table(title=f"Last {len(entries)} Usage Entries")
    table.add_column("Timestamp", style="cyan")
    table.add_column("Model", style="cyan")
    table.add_column("Caller", style="cyan")
    table.add_column("User", style="cyan")
    table.add_column("Prompt Tokens", justify="right", style="green")
    table.add_column("Completion Tokens", justify="right", style="green")
    table.add_column("Total Tokens", justify="right", style="green")
    table.add_column("Cost", justify="right", style="green")
    table.add_column("Exec Time", justify="right", style="green")

    for entry in entries:
        table.add_row(
            entry.timestamp.strftime("%Y-%m-%d %H:%M:%S") if entry.timestamp else "-",
            entry.model,
            entry.caller_name or "-",
            entry.username or "-",
            format_tokens(entry.prompt_tokens if entry.prompt_tokens is not None else 0),
            format_tokens(entry.completion_tokens if entry.completion_tokens is not None else 0),
            format_tokens(entry.total_tokens if entry.total_tokens is not None else 0),
            f"${format_float(entry.cost)}",
            format_time(entry.execution_time)
        )

    console.print(table)


@cli.command()
@click.option('--query', 'query', required=True, help='Custom SQL SELECT query to execute')
@click.option('--format', 'output_format', type=click.Choice(['table', 'csv']), default='table', help='Output format')
@with_accounting
def select(ctx, accounting: LLMAccounting, query, output_format):
    """Execute a custom SELECT query on the database"""
    results = accounting.backend.execute_query(query)
    
    if not results:
        console.print("[yellow]No results found[/yellow]")
        return

    if output_format == 'table':
        # Create table for results
        table = Table(title="Query Results")
        for col in results[0].keys():
            table.add_column(col, style="cyan")

        for row in results:
            table.add_row(*[str(value) for value in row.values()])

        console.print(table)
    elif output_format == 'csv':
        # Print CSV header
        print(",".join(results[0].keys()))
        # Print CSV rows
        for row in results:
            print(",".join([str(value) for value in row.values()]))

@cli.command()
@click.option('--model', required=True, help='Name of the LLM model')
@click.option('--prompt-tokens', type=int, help='Number of prompt tokens')
@click.option('--completion-tokens', type=int, help='Number of completion tokens')
@click.option('--total-tokens', type=int, help='Total number of tokens')
@click.option('--local-prompt-tokens', type=int, help='Number of locally counted prompt tokens')
@click.option('--local-completion-tokens', type=int, help='Number of locally counted completion tokens')
@click.option('--local-total-tokens', type=int, help='Total number of locally counted tokens')
@click.option('--cost', type=float, required=True, help='Cost of the API call')
@click.option('--execution-time', type=float, required=True, help='Execution time in seconds')
@click.option('--timestamp', type=click.DateTime(), help='Timestamp of the usage (default: current time)')
@click.option('--caller-name', help='Name of the calling application')
@click.option('--username', help='Name of the user')
@click.option('--cached-tokens', type=int, default=0, help='Number of tokens retrieved from cache')
@click.option('--reasoning-tokens', type=int, default=0, help='Number of tokens used for model reasoning')
@with_accounting
def track(ctx, accounting: LLMAccounting, model, prompt_tokens, completion_tokens, total_tokens, local_prompt_tokens, local_completion_tokens,
          local_total_tokens, cost, execution_time, timestamp, caller_name, username, cached_tokens, reasoning_tokens):
    """Track a new LLM usage entry"""
    accounting.track_usage(
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        local_prompt_tokens=local_prompt_tokens,
        local_completion_tokens=local_completion_tokens,
        local_total_tokens=local_total_tokens,
        cost=cost,
        execution_time=execution_time,
        timestamp=timestamp,
        caller_name=caller_name or "",
        username=username or "",
        cached_tokens=cached_tokens,
        reasoning_tokens=reasoning_tokens
    )
    console.print("[green]Usage entry tracked successfully[/green]")

def main():
    """Entry point for the CLI
    
    Available commands:
      purge    Delete all usage entries from the database
      select   Execute a custom SELECT query on the database
      stats    Show usage statistics
      tail     Show the most recent usage entries
      track    Track a new LLM usage entry
    """
    cli(prog_name='llm-accounting')
