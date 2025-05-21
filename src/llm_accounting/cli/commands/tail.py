from rich.table import Table

from llm_accounting import LLMAccounting

from ..utils import console, format_float, format_time, format_tokens


def run_tail(args, accounting: LLMAccounting):
    """Show the most recent usage entries"""
    entries = accounting.tail(args.number)

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
            format_tokens(
                entry.prompt_tokens if entry.prompt_tokens is not None else 0
            ),
            format_tokens(
                entry.completion_tokens if entry.completion_tokens is not None else 0
            ),
            format_tokens(entry.total_tokens if entry.total_tokens is not None else 0),
            f"${format_float(entry.cost)}",
            format_time(entry.execution_time),
        )

    console.print(table)
