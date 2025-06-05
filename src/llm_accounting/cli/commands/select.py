from rich.table import Table
import sqlite3 # Import for parameter handling if needed, though backend handles it
import sys # Import sys for sys.exit

from llm_accounting import LLMAccounting
from ..utils import console

def run_select(args, accounting: LLMAccounting):
    """Execute a custom SELECT query or filter entries on the database"""
    query_to_execute = ""
    params = []

    if args.query:
        if args.project:
            console.print("[yellow]Warning: --project argument is ignored when --query is specified.[/yellow]")
        query_to_execute = args.query
    else:
        base_query = "SELECT * FROM accounting_entries"
        conditions = []
        if args.project:
            if args.project.upper() == "NULL":
                conditions.append("project IS NULL")
            else:
                import re
                if not re.fullmatch(r"[\w-]+", args.project):
                    console.print("[red]Invalid project name provided.[/red]")
                    sys.exit(1)
                safe_project = args.project.replace("'", "''")
                conditions.append(f"project = '{safe_project}'")

        if conditions:
            base_query += " WHERE " + " AND ".join(conditions)
        query_to_execute = base_query + ";"

    if not query_to_execute:
        console.print("[red]No query to execute. Provide --query or filter criteria like --project.[/red]")
        return # Or sys.exit(1) if preferred for this case as well

    # This is where the limitation is: accounting.backend.execute_query(query_string_only)
    # If execute_query supported params: results = accounting.backend.execute_query(query_to_execute, params)
    # For now, if params were meant to be used (they are not, due to string formatting above),
    # the call would fail or be incorrect.
    try:
        results = accounting.backend.execute_query(query_to_execute)
    except Exception as e:
        console.print(f"[red]Error executing query: {e}[/red]")
        # Note: If the error is due to string formatting for non-string project names,
        # that's a consequence of the current execute_query limitation.
        # Example: If project name was `My Project's Name`, the single quote would break the SQL.
        sys.exit(1) # MODIFIED_LINE


    if not results:
        console.print("[yellow]No results found[/yellow]")
        return

    if args.format == "table":
        table = Table(title="Query Results")
        if results: # Ensure there are results before trying to get keys
            for col in results[0].keys():
                table.add_column(col, style="cyan")

            for row in results:
                table.add_row(*[str(value) if value is not None else "N/A" for value in row.values()])
        else: # Should be caught by "No results found" earlier, but as a safeguard
            console.print("[yellow]No results to display in table.[/yellow]")
            return

        console.print(table)
    elif args.format == "csv":
        if results: # Ensure there are results
            print(",".join(results[0].keys()))
            for row in results:
                print(",".join([str(value) if value is not None else "" for value in row.values()]))
        else: # Safeguard
            console.print("[yellow]No results to display in CSV.[/yellow]")
            return
