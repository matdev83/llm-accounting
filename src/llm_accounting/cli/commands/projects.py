from llm_accounting import LLMAccounting
from ..utils import console


def run_project_add(args, accounting: LLMAccounting) -> None:
    accounting.quota_service.create_project(args.name)
    console.print(f"[green]Project '{args.name}' added.[/green]")


def run_project_list(args, accounting: LLMAccounting) -> None:
    projects = accounting.quota_service.list_projects()
    if not projects:
        console.print("[yellow]No projects defined.[/yellow]")
    else:
        for p in projects:
            console.print(p)


def run_project_update(args, accounting: LLMAccounting) -> None:
    accounting.quota_service.update_project(args.name, args.new_name)
    console.print(f"[green]Project '{args.name}' renamed to '{args.new_name}'.[/green]")


def run_project_delete(args, accounting: LLMAccounting) -> None:
    accounting.quota_service.delete_project(args.name)
    console.print(f"[green]Project '{args.name}' deleted.[/green]")
