from rich.table import Table

from llm_accounting import LLMAccounting

from ..utils import console


def run_select(args, accounting: LLMAccounting):
    """Execute a custom SELECT query on the database"""
    console.print("[red]Error: Arbitrary SQL queries are no longer supported for security reasons.[/red]")
    console.print("[yellow]Please use specific commands or methods to access data.[/yellow]")
