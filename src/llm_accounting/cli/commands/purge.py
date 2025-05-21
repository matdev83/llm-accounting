from rich.prompt import Confirm

from llm_accounting import LLMAccounting

from ..utils import console


def run_purge(args, accounting: LLMAccounting):
    """Delete all usage entries from the database"""
    if not args.yes:
        if not Confirm.ask(
            "Are you sure you want to delete all usage entries? This action cannot be undone."
        ):
            console.print("[yellow]Purge operation cancelled[/yellow]")
            return

    accounting.purge()
    console.print("[green]All usage entries have been deleted[/green]")
