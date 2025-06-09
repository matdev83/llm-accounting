from llm_accounting import LLMAccounting
from ..utils import console


def run_user_add(args, accounting: LLMAccounting) -> None:
    accounting.quota_service.create_user(args.name, ou_name=args.ou_name, email=args.email)
    console.print(f"[green]User '{args.name}' added.[/green]")


def run_user_list(args, accounting: LLMAccounting) -> None:
    users = accounting.quota_service.list_users()
    if not users:
        console.print("[yellow]No users defined.[/yellow]")
    else:
        for u in users:
            status = "active" if u["enabled"] else "inactive"
            console.print(f"{u['user_name']} ({status})")


def run_user_update(args, accounting: LLMAccounting) -> None:
    accounting.quota_service.update_user(args.name, args.new_name)
    console.print(f"[green]User '{args.name}' renamed to '{args.new_name}'.[/green]")


def run_user_deactivate(args, accounting: LLMAccounting) -> None:
    accounting.quota_service.set_user_active(args.name, False)
    console.print(f"[green]User '{args.name}' deactivated.[/green]")
