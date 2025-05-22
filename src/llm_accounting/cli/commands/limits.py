import argparse
from typing import Any, Dict, List, Optional

from llm_accounting.models.limits import LimitScope, LimitType, TimeInterval
from llm_accounting.services.quota_service import QuotaService
from llm_accounting import LLMAccounting
from llm_accounting.cli.utils import console

def set_limit(args: argparse.Namespace, accounting: LLMAccounting):
    """Sets a new usage limit."""
    try:
        accounting.set_usage_limit(
            scope=LimitScope(args.scope.upper()),
            limit_type=LimitType(args.limit_type.lower()),
            max_value=args.max_value,
            interval_unit=TimeInterval(args.interval_unit.lower()),
            interval_value=args.interval_value,
            model=args.model,
            username=args.username,
            caller_name=args.caller_name,
        )
        console.print(f"[green]Usage limit set successfully.[/green]")
    except Exception as e:
        console.print(f"[red]Error setting limit: {e}[/red]")

def list_limits(args: argparse.Namespace, accounting: LLMAccounting):
    """Lists all configured usage limits."""
    try:
        limits = accounting.get_usage_limits()
        if not limits:
            console.print("[yellow]No usage limits configured.[/yellow]")
            return

        console.print("[bold]Configured Usage Limits:[/bold]")
        for limit in limits:
            scope_details = []
            if limit.model is not None:
                scope_details.append(f"Model: {limit.model}")
            if limit.username is not None:
                scope_details.append(f"User: {limit.username}")
            if limit.caller_name is not None:
                scope_details.append(f"Caller: {limit.caller_name}")
            
            scope_str = f" ({', '.join(scope_details)})" if scope_details else ""
            
            console.print(
                f"  [cyan]ID:[/cyan] {limit.id}, "
                f"[cyan]Scope:[/cyan] {limit.scope}{scope_str}, "
                f"[cyan]Type:[/cyan] {limit.limit_type}, "
                f"[cyan]Max Value:[/cyan] {limit.max_value}, "
                f"[cyan]Interval:[/cyan] {limit.interval_value} {limit.interval_unit}"
            )
    except Exception as e:
        console.print(f"[red]Error listing limits: {e}[/red]")

def delete_limit(args: argparse.Namespace, accounting: LLMAccounting):
    """Deletes a usage limit by its ID."""
    try:
        accounting.delete_usage_limit(args.id)
        console.print(f"[green]Usage limit with ID {args.id} deleted successfully.[/green]")
    except Exception as e:
        console.print(f"[red]Error deleting limit: {e}[/red]")
