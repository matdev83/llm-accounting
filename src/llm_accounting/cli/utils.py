from rich.console import Console

from llm_accounting import LLMAccounting

from ..backends.sqlite import SQLiteBackend
from ..backends.neon import NeonBackend

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


def get_accounting(db_backend: str, db_file: str = None, neon_connection_string: str = None):
    """Get an LLMAccounting instance with the specified backend"""
    if db_backend == "sqlite":
        if not db_file:
            console.print("[red]Error: --db-file is required for sqlite backend.[/red]")
            raise SystemExit(1)
        backend = SQLiteBackend(db_path=db_file)
    elif db_backend == "neon":
        if not neon_connection_string:
            console.print("[red]Error: --neon-connection-string is required for neon backend.[/red]")
            raise SystemExit(1)
        backend = NeonBackend(neon_connection_string=neon_connection_string)
    else:
        console.print(f"[red]Error: Unknown database backend '{db_backend}'.[/red]")
        raise SystemExit(1)

    acc = LLMAccounting(backend=backend)
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
