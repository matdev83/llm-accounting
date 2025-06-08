from rich.table import Table
import sys
import re # For project name validation
from typing import List, Dict, Any # For type hints

from llm_accounting import LLMAccounting
from ..utils import console

# --- START NEW HELPER FUNCTIONS ---

def _construct_query(args) -> str:
    query_to_execute = ""
    if args.query:
        if args.project: # Project flag is ignored if a full query is given
            console.print("[yellow]Warning: --project argument is ignored when --query is specified.[/yellow]")
        query_to_execute = args.query
    else:
        # Construct query based on filters if no direct query is provided
        base_query = "SELECT * FROM accounting_entries"
        conditions = []
        # Project filter
        if args.project:
            if args.project.upper() == "NULL":
                conditions.append("project IS NULL")
            else:
                # Allow alphanumeric, hyphens, and dots in project names
                if not re.fullmatch(r"[\w\-\.]+", args.project):
                    console.print(f"[red]Invalid project name '{args.project}'. Project names can only contain alphanumeric characters, hyphens, and dots.[/red]")
                    sys.exit(1)
                safe_project = args.project.replace("'", "''")
                conditions.append(f"project = '{safe_project}'")

        if conditions:
            base_query += " WHERE " + " AND ".join(conditions)
        query_to_execute = base_query + ";"

    return query_to_execute

def _display_results(results: List[Dict[str, Any]], format_type: str) -> None:
    if not results:
        console.print("[yellow]No results found[/yellow]")
        return

    if format_type == "table":
        table = Table(title="Query Results")
        headers = results[0].keys()
        for col in headers:
            table.add_column(col, style="cyan")

        for row in results:
            table.add_row(*[str(row.get(header)) if row.get(header) is not None else "N/A" for header in headers])
        console.print(table)
    elif format_type == "csv":
        headers = results[0].keys()
        print(",".join(headers))
        for row in results:
            print(",".join([str(row.get(header)) if row.get(header) is not None else "" for header in headers]))

# --- END NEW HELPER FUNCTIONS ---

def run_select(args, accounting: LLMAccounting):
    """Execute a custom SELECT query or filter entries on the database"""
    query_to_execute = _construct_query(args)

    if not query_to_execute:
        console.print("[red]No query to execute. Provide --query or filter criteria like --project.[/red]")
        sys.exit(1) # Exit if _construct_query somehow returns an empty string (should not happen with current logic)

    try:
        results = accounting.backend.execute_query(query_to_execute)
    except ValueError as ve:
        console.print(f"[red]Error executing query: {ve}[/red]") # Corrected message
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error executing query: {e}[/red]") # General error
        sys.exit(1)

    _display_results(results, args.format)
