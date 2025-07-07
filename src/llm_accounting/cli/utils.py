import os
import platform
from rich.console import Console
from typing import Optional

from ..backends.base import BaseBackend

from llm_accounting import LLMAccounting

from llm_accounting.backends.sqlite import SQLiteBackend
from llm_accounting.backends.postgresql import PostgreSQLBackend

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


def _create_backend(backend_type: str, db_file: Optional[str], connection_string: Optional[str], purpose: str = "database") -> BaseBackend:
    """Helper to create a backend instance."""
    if backend_type == "sqlite":
        if not db_file:
            console.print(f"[red]Error: --{'audit-' if 'audit' in purpose else ''}db-file is required for sqlite {purpose} backend.[/red]")
            raise SystemExit(1)
        return SQLiteBackend(db_path=db_file)
    elif backend_type == "postgresql":
        effective_connection_string = connection_string or os.environ.get(
            "AUDIT_POSTGRESQL_CONNECTION_STRING" if "audit" in purpose else "POSTGRESQL_CONNECTION_STRING"
        )
        if not effective_connection_string:
            console.print(f"[red]Error: --{'audit-' if 'audit' in purpose else ''}postgresql-connection-string is required for postgresql {purpose} backend.[/red]")
            raise SystemExit(1)
        return PostgreSQLBackend(postgresql_connection_string=effective_connection_string)
    else:
        console.print(f"[red]Error: Unknown {purpose} backend '{backend_type}'.[/red]")
        raise SystemExit(1)


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
    enforce_project_names: bool = False,
    enforce_user_names: bool = False,
):
    """Get an LLMAccounting instance with the specified backend"""
    backend = _create_backend(db_backend, db_file, postgresql_connection_string, purpose="database")

    # Configure audit backend
    if not audit_db_backend and not audit_db_file and not audit_postgresql_connection_string:
        audit_backend = backend  # Use the main backend if no specific audit backend is configured
    else:
        effective_audit_backend_type = audit_db_backend or db_backend
        audit_backend = _create_backend(
            effective_audit_backend_type,
            audit_db_file or db_file, # Use main db_file as fallback if audit_db_file not given
            audit_postgresql_connection_string, # Specific audit connection string
            purpose="audit database"
        )

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
        enforce_project_names=enforce_project_names,
        enforce_user_names=enforce_user_names,
    )
    return acc


# TODO: Vulture - Dead code? Verify if used externally or planned for future use before removing.
# def with_accounting(f):  # type: ignore
#     def wrapper(args, accounting_instance, *args_f, **kwargs_f):
#         try:
#             with accounting_instance:
#                 return f(args, accounting_instance, *args_f, **kwargs_f)
#         except (ValueError, PermissionError, OSError, RuntimeError) as e:  # type: ignore
#             console.print(f"[red]Error: {e}[/red]")
#             raise  # Re-raise the exception
#         except SystemExit:
#             raise
#         except Exception as e:  # type: ignore
#             console.print(f"[red]Unexpected error: {e}[/red]")
#             raise  # Re-raise the exception
#
#     return wrapper
