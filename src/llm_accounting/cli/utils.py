from rich.console import Console

from .. import LLMAccounting
from ..backends.sqlite import SQLiteBackend

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

def get_accounting(db_file=None):
    """Get an LLMAccounting instance with SQLite backend"""
    backend = SQLiteBackend(db_path=db_file)
    acc = LLMAccounting(backend=backend)
    # The context manager will handle __enter__ and __exit__
    return acc

def with_accounting(f):
    def wrapper(args, accounting_instance, *args_f, **kwargs_f):
        try:
            with accounting_instance:
                return f(args, accounting_instance, *args_f, **kwargs_f)
        except (ValueError, PermissionError, OSError, RuntimeError) as e:
            console.print(f"[red]Error: {e}[/red]")
            raise # Re-raise the exception
        except SystemExit:
            raise
        except Exception as e:
            console.print(f"[red]Unexpected error: {e}[/red]")
            raise # Re-raise the exception
    return wrapper
