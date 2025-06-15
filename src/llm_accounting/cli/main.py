import argparse
import sys
import os
import platform
from importlib.metadata import version as get_version

from .parsers import (add_purge_parser, add_select_parser, add_stats_parser,
                      add_tail_parser, add_track_parser, add_limits_parser,
                      add_log_event_parser, add_projects_parser, add_users_parser)
from .utils import console


def _check_privileged_user():
    """
    Checks if the current user is a privileged user (root on Linux/macOS, admin on Windows).
    Exits the program with an error message if the user is privileged.
    """
    if os.environ.get("PYTEST_CURRENT_TEST") is not None or os.environ.get("LLM_ACCOUNTING_ALLOW_ROOT"):
        return

    if platform.system() == "Windows":
        try:
            import ctypes
            if ctypes.windll.shell32.IsUserAnAdmin():
                console.print("[red]Error: Running the CLI as an administrator is not allowed for security reasons.[/red]")
                sys.exit(1)
        except AttributeError:
            pass
    elif hasattr(os, 'geteuid') and os.geteuid() == 0:  # type: ignore
        console.print("[red]Error: Running the CLI as root is not allowed for security reasons.[/red]")
        sys.exit(1)


def main():
    _check_privileged_user()
    package_version = get_version('llm-accounting')
    parser = argparse.ArgumentParser(
        description=(
            "LLM Accounting CLI - Track and analyze LLM usage. "
            "Limits support '*' wildcards and max values of 0 (deny) or -1 (unlimited). "
            "Audit logs can use a separate database via --audit-db-* options."
        ),
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
        choices=["sqlite", "postgresql"],
        help="Select the database backend (sqlite, postgresql, or csv). Defaults to 'sqlite'.",
    )
    parser.add_argument(
        "--postgresql-connection-string",
        type=str,
        help="Connection string for the PostgreSQL database. "
             "Required when --db-backend is 'postgresql'. "
             "Can also be provided via POSTGRESQL_CONNECTION_STRING environment variable.",
    )
    parser.add_argument(
        "--project-name",
        type=str,
        help="Default project name to associate with usage entries. Can be overridden by command-specific --project.",
    )
    parser.add_argument(
        "--app-name",
        type=str,
        help="Default application name to associate with usage entries. Can be overridden by command-specific --caller-name.",
    )
    parser.add_argument(
        "--user-name",
        type=str,
        help="Default user name to associate with usage entries. Can be overridden by command-specific --username. Defaults to current system user.",
    )
    parser.add_argument(
        "--enforce-project-names",
        action="store_true",
        help="Reject operations using project names not present in the project dictionary.",
    )
    parser.add_argument(
        "--enforce-user-names",
        action="store_true",
        help="Reject operations using user names not present in the user dictionary.",
    )
    parser.add_argument(
        "--audit-db-backend",
        type=str,
        choices=["sqlite", "postgresql"],
        help="Backend for audit logs. Defaults to the value of --db-backend if not provided.",
    )
    parser.add_argument(
        "--audit-db-file",
        type=str,
        help="SQLite database file path for audit logs. Only applicable when the audit DB backend is 'sqlite'.",
    )
    parser.add_argument(
        "--audit-postgresql-connection-string",
        type=str,
        help="Connection string for the PostgreSQL audit log database. Required when audit DB backend is 'postgresql'. Can also be provided via AUDIT_POSTGRESQL_CONNECTION_STRING environment variable.",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    add_stats_parser(subparsers)
    add_purge_parser(subparsers)
    add_tail_parser(subparsers)
    add_select_parser(subparsers)
    add_track_parser(subparsers)
    add_limits_parser(subparsers)
    add_log_event_parser(subparsers)
    add_projects_parser(subparsers)
    add_users_parser(subparsers)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    from .utils import get_accounting

    try:
        kwargs = dict(
            db_backend=args.db_backend,
            db_file=args.db_file,
            postgresql_connection_string=args.postgresql_connection_string,
            audit_db_backend=args.audit_db_backend,
            audit_db_file=args.audit_db_file,
            audit_postgresql_connection_string=args.audit_postgresql_connection_string,
            project_name=args.project_name,
            app_name=args.app_name,
            user_name=args.user_name,
        )
        if args.enforce_project_names:
            kwargs["enforce_project_names"] = True
        if args.enforce_user_names:
            kwargs["enforce_user_names"] = True
        accounting = get_accounting(**kwargs)
        with accounting:
            args.func(args, accounting)
    except SystemExit:
        raise
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
