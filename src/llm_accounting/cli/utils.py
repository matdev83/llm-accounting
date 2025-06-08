import os
import platform
from rich.console import Console
from typing import Optional

from llm_accounting import LLMAccounting

from ..backends.sqlite import SQLiteBackend
from ..backends.postgresql import PostgreSQLBackend

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
    audit_db_backend: Optional[str] = None,
    audit_db_file: Optional[str] = None,
    audit_postgresql_connection_string: Optional[str] = None,
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
    else:
        console.print(f"[red]Error: Unknown database backend '{db_backend}'.[/red]")
        raise SystemExit(1)

    # Configure audit backend
    if not audit_db_backend and not audit_db_file and not audit_postgresql_connection_string:
        audit_backend = backend
    else:
        effective_audit_backend = audit_db_backend or db_backend
        if effective_audit_backend == "sqlite":
            audit_path = audit_db_file or db_file
            if not audit_path:
                console.print("[red]Error: --audit-db-file is required for sqlite audit backend.[/red]")
                raise SystemExit(1)
            audit_backend = SQLiteBackend(db_path=audit_path)
        elif effective_audit_backend == "postgresql":
            conn_str = audit_postgresql_connection_string or postgresql_connection_string or os.environ.get("AUDIT_POSTGRESQL_CONNECTION_STRING")
            if not conn_str:
                console.print("[red]Error: --audit-postgresql-connection-string is required for postgresql audit backend.[/red]")
                raise SystemExit(1)
            audit_backend = PostgreSQLBackend(postgresql_connection_string=conn_str)
        else:
            console.print(f"[red]Error: Unknown audit database backend '{effective_audit_backend}'.[/red]")
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
        audit_backend=audit_backend,
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
