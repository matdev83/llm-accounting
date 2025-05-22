from rich.table import Table

from llm_accounting import LLMAccounting

from ..utils import console


def run_select(args, accounting: LLMAccounting):
    """Execute a custom SELECT query on the database"""
    results = accounting.backend.execute_query(args.query)

    if not results:
        console.print("[yellow]No results found[/yellow]")
        return

    if args.format == "table":
        # Create table for results
        table = Table(title="Query Results")
        for col in results[0].keys():
            table.add_column(col, style="cyan")

        for row in results:
            table.add_row(*[str(value) for value in row.values()])

        console.print(table)
    elif args.format == "csv":
        # Print CSV header
        print(",".join(results[0].keys()))
        # Print CSV rows
        for row in results:
            print(",".join([str(value) for value in row.values()]))
