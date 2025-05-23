import argparse
import sys
from importlib.metadata import version as get_version

from .parsers import (add_purge_parser, add_select_parser, add_stats_parser,
                      add_tail_parser, add_track_parser, add_limits_parser)
from .utils import console


def main():
    package_version = get_version('llm-accounting')
    parser = argparse.ArgumentParser(
        description="LLM Accounting CLI - Track and analyze LLM usage",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument('--version', action='version', version=f'llm-accounting {package_version}')
    parser.add_argument(
        "--db-file",
        type=str,
        help="SQLite database file path (must end with .sqlite, .sqlite3 or .db). "
             "Only applicable when --db-backend is 'sqlite'.",
    )
    parser.add_argument(
        "--db-backend",
        type=str,
        default="sqlite",
        choices=["sqlite", "neon"],
        help="Select the database backend (sqlite or neon). Defaults to 'sqlite'.",
    )
    parser.add_argument(
        "--neon-connection-string",
        type=str,
        help="Connection string for the Neon database. "
             "Required when --db-backend is 'neon'. "
             "Can also be provided via NEON_CONNECTION_STRING environment variable.",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    add_stats_parser(subparsers)
    add_purge_parser(subparsers)
    add_tail_parser(subparsers)
    add_select_parser(subparsers)
    add_track_parser(subparsers)
    add_limits_parser(subparsers)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    from .utils import get_accounting

    try:
        accounting = get_accounting(
            db_backend=args.db_backend,
            db_file=args.db_file,
            neon_connection_string=args.neon_connection_string
        )
        with accounting:
            args.func(args, accounting)
    except SystemExit:
        # Allow SystemExit to propagate, especially for pytest.raises
        raise
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
