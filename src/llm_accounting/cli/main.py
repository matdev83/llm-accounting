import argparse
import sys

from .parsers import (add_purge_parser, add_select_parser, add_stats_parser,
                      add_tail_parser, add_track_parser)
from .utils import console


def main():
    parser = argparse.ArgumentParser(
        description="LLM Accounting CLI - Track and analyze LLM usage",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--db-file",
        type=str,
        help="SQLite database file path (must end with .sqlite, .sqlite3 or .db)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    add_stats_parser(subparsers)
    add_purge_parser(subparsers)
    add_tail_parser(subparsers)
    add_select_parser(subparsers)
    add_track_parser(subparsers)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    from .utils import get_accounting

    try:
        accounting = get_accounting(db_file=args.db_file)
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
