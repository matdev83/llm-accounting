import argparse
from typing import Any, Dict, List

from llm_accounting import LLMAccounting
from llm_accounting.models.limits import LimitScope, LimitType, TimeInterval, UsageLimitDTO
from llm_accounting.cli.utils import console


def set_limit(args: argparse.Namespace, accounting: LLMAccounting):
    """Sets a new usage limit."""
    try:
        if args.scope.upper() == LimitScope.PROJECT.value and not args.project_name:
            console.print(f"[red]Error: --project-name is required when scope is {LimitScope.PROJECT.value}.[/red]")
            return

        accounting.set_usage_limit(
            scope=LimitScope(args.scope.upper()),
            limit_type=LimitType(args.limit_type.lower()),
            max_value=args.max_value,
            interval_unit=TimeInterval(args.interval_unit.lower()),
            interval_value=args.interval_value,
            model=args.model,
            username=args.username,
            caller_name=args.caller_name,
            project_name=args.project_name
        )
        console.print("[green]Usage limit set successfully.[/green]")
    except ValueError as ve:
        console.print(f"[red]Error setting limit: {ve}[/red]")
    except Exception as e:
        console.print(f"[red]An unexpected error occurred while setting limit: {e}[/red]")


def list_limits(args: argparse.Namespace, accounting: LLMAccounting):
    """Lists all configured usage limits, with optional filters."""
    try:
        filters: Dict[str, Any] = {
            k: v for k, v in {
                'scope': LimitScope(args.scope.upper()) if args.scope else None,
                'model': args.model,
                'username': args.username,
                'caller_name': args.caller_name,
                'project_name': args.project_name
            }.items() if v is not None
        }

        limits: List[UsageLimitDTO] = accounting.get_usage_limits(**filters)

        if not limits:
            console.print("[yellow]No usage limits found matching the criteria.[/yellow]")
            return

        console.print("[bold]Configured Usage Limits:[/bold]")
        for limit in limits:
            details = []
            if limit.model:
                details.append(f"Model: {limit.model}")
            if limit.username:
                details.append(f"User: {limit.username}")
            if limit.caller_name:
                details.append(f"Caller: {limit.caller_name}")
            if limit.project_name:
                details.append(f"Project: {limit.project_name}")
            
            details_str = f" ({', '.join(details)})" if details else ""
            
            console.print(
                f"  [cyan]ID:[/cyan] {limit.id}, "
                f"[cyan]Scope:[/cyan] {limit.scope}{details_str}, "
                f"[cyan]Type:[/cyan] {limit.limit_type}, "
                f"[cyan]Max Value:[/cyan] {limit.max_value}, "
                f"[cyan]Interval:[/cyan] {limit.interval_value} {limit.interval_unit}"
            )
    except ValueError as ve:
        console.print(f"[red]Error listing limits: {ve}[/red]")
    except Exception as e:
        console.print(f"[red]An unexpected error occurred while listing limits: {e}[/red]")


def delete_limit(args: argparse.Namespace, accounting: LLMAccounting):
    """Deletes a usage limit by its ID."""
    try:
        accounting.delete_usage_limit(args.id)
        console.print(f"[green]Usage limit with ID {args.id} deleted successfully.[/green]")
    except Exception as e:
        console.print(f"[red]Error deleting limit (ID: {args.id}): {e}[/red]")
