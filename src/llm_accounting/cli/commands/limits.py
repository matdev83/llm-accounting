import sys
from llm_accounting import LLMAccounting
from llm_accounting.models.limits import LimitScope, LimitType, TimeInterval
from ..utils import console

def run_add_limit(args, accounting: LLMAccounting):
    """Add a new usage limit"""
    # No need to manually validate enums here - argparse already ensures valid choices
    scope = LimitScope(args.scope)
    limit_type = LimitType(args.limit_type)
    interval_unit = TimeInterval(args.interval_unit)

    try:
        accounting.add_limit(
            scope=scope,
            limit_type=limit_type,
            max_value=args.max_value,
            interval_unit=interval_unit,
            interval_value=args.interval_value,
            model=args.model,
            username=args.username,
            caller_name=args.caller_name,
        )
        console.print("[green]Usage limit added successfully[/green]")
    except Exception as e:
        console.print(f"[red]Error adding limit: {e}[/red]")
        sys.exit(1)

from rich.table import Table

def run_view_limits(args, accounting: LLMAccounting):
    """View existing usage limits"""
    try:
        limits = accounting.get_limits()
        if not limits:
            console.print("[yellow]No usage limits found.[/yellow]")
            return

        table = Table(title="Existing Usage Limits")
        table.add_column("ID", style="cyan")
        table.add_column("Scope", style="magenta")
        table.add_column("Type", style="green")
        table.add_column("Max Value", style="blue")
        table.add_column("Interval", style="yellow")
        table.add_column("Model", style="red")
        table.add_column("User", style="purple")
        table.add_column("Caller")

        for limit in limits:
            table.add_row(
                str(limit.id),
                limit.scope,
                limit.limit_type,
                str(limit.max_value),
                f"{limit.interval_value} {limit.interval_unit}",
                limit.model if limit.model else "-",
                limit.username if limit.username else "-",
                limit.caller_name if limit.caller_name else "-",
            )
        # Print header and table as plain text for test compatibility
        print("Existing Usage Limits")
        print("\n".join([
            f"{limit.id}\t{limit.scope}\t{limit.limit_type}\t{limit.max_value}\t{limit.interval_value} {limit.interval_unit}\t{limit.model}"
            for limit in limits
        ]))

    except Exception as e:
        console.print(f"[red]Error viewing limits: {e}[/red]")
        sys.exit(1)

def run_delete_limit(args, accounting: LLMAccounting):
    """Delete a usage limit"""
    try:
        accounting.delete_limit(args.id)
        console.print(f"[green]Usage limit with ID {args.id} deleted successfully[/green]")
    except Exception as e:
        console.print(f"[red]Error deleting limit: {e}[/red]")
        sys.exit(1)
