from llm_accounting import LLMAccounting
from ..utils import console


def run_user_add(args, accounting: LLMAccounting) -> None:
    accounting.quota_service.create_user(args.user_name, args.ou_name, args.email)
    console.print(f"[green]User '{args.user_name}' added.[/green]")


def run_user_list(args, accounting: LLMAccounting) -> None:
    users = accounting.quota_service.list_users()
    if not users:
        console.print("[yellow]No users defined.[/yellow]")
    else:
        for name in users:
            console.print(name)


def run_user_update(args, accounting: LLMAccounting) -> None:
    accounting.quota_service.update_user(
        args.user_name,
        new_user_name=args.new_user_name,
        ou_name=args.ou_name,
        email=args.email,
    )
    console.print(f"[green]User '{args.user_name}' updated.[/green]")


def run_user_deactivate(args, accounting: LLMAccounting) -> None:
    accounting.quota_service.set_user_enabled(args.user_name, False)
    console.print(f"[green]User '{args.user_name}' deactivated.[/green]")
