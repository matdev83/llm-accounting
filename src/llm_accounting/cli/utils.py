import os
import platform
from rich.console import Console
from typing import Optional

from llm_accounting import LLMAccounting

from ..backends.sqlite import SQLiteBackend
from ..backends.postgresql import PostgreSQLBackend
from ..backends.csv_backend import CSVBackend

console = Console()


def format_float(value: float) -> str:
    """Format float values for display"""
    return f"{value:.4f}" if value else "0.0000"


def format_time(value: float) -> str:
    """Format time values for display"""
    return f"{value:.2f}s" if value else "0.00s"


def format_tokens(value: int) -> str:
    """Format token counts for display"""
    return f"{value:,}" if value else "0"


def get_accounting(
    db_backend: str,
    db_file: Optional[str] = None,
    postgresql_connection_string: Optional[str] = None,
    csv_data_dir: Optional[str] = None, # Added new parameter
    project_name: Optional[str] = None,
    app_name: Optional[str] = None,
    user_name: Optional[str] = None,
):
    """Get an LLMAccounting instance with the specified backend"""
    if db_backend == "sqlite":
        if not db_file:
            console.print("[red]Error: --db-file is required for sqlite backend.[/red]")
            raise SystemExit(1)
        backend = SQLiteBackend(db_path=db_file)
    elif db_backend == "postgresql":
        if not postgresql_connection_string:
            console.print("[red]Error: --postgresql-connection-string is required for postgresql backend.[/red]")
            raise SystemExit(1)
        backend = PostgreSQLBackend(postgresql_connection_string=postgresql_connection_string)
    elif db_backend == "csv":
        # csv_data_dir will have a default from argparse if not provided by user.
        # If it somehow becomes None, CSVBackend's own default will apply if we pass None.
        backend = CSVBackend(csv_data_dir=csv_data_dir)
    else:
        console.print(f"[red]Error: Unknown database backend '{db_backend}'.[/red]")
        raise SystemExit(1)

    # Determine default username if not provided
    if user_name is None:
        if platform.system() == "Windows":
            default_user_name = os.environ.get("USERNAME")
        else:
            default_user_name = os.environ.get("USER")
    else:
        default_user_name = user_name

    acc = LLMAccounting(
        backend=backend,
        project_name=project_name,
        app_name=app_name,
        user_name=default_user_name,
    )
    return acc


def with_accounting(f):
    def wrapper(args, accounting_instance, *args_f, **kwargs_f):
        try:
            with accounting_instance:
                return f(args, accounting_instance, *args_f, **kwargs_f)
        except (ValueError, PermissionError, OSError, RuntimeError) as e:
            console.print(f"[red]Error: {e}[/red]")
            raise  # Re-raise the exception
        except SystemExit:
            raise
        except Exception as e:
            console.print(f"[red]Unexpected error: {e}[/red]")
            raise  # Re-raise the exception

    return wrapper
