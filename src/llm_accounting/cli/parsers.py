from llm_accounting.cli.commands.purge import run_purge
from llm_accounting.cli.commands.select import run_select
from llm_accounting.cli.commands.stats import run_stats
from llm_accounting.cli.commands.tail import run_tail
from llm_accounting.cli.commands.track import run_track
from llm_accounting.cli.commands.limits import run_add_limit, run_view_limits, run_delete_limit
from llm_accounting.models.limits import LimitScope, LimitType, TimeInterval


def add_stats_parser(subparsers):
    stats_parser = subparsers.add_parser("stats", help="Show usage statistics")
    stats_parser.add_argument(
        "--period",
        type=str,
        choices=["daily", "weekly", "monthly", "yearly"],
        help="Show stats for specific period "
             "(daily, weekly, monthly, or yearly)",
    )
    stats_parser.add_argument(
        "--start", type=str, help="Start date for custom period (YYYY-MM-DD)"
    )
    stats_parser.add_argument(
        "--end", type=str, help="End date for custom period (YYYY-MM-DD)"
    )
    stats_parser.set_defaults(func=run_stats)


def add_purge_parser(subparsers):
    purge_parser = subparsers.add_parser(
        "purge", help="Delete all usage entries from the database"
    )
    purge_parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip confirmation prompt"
    )
    purge_parser.set_defaults(func=run_purge)


def add_tail_parser(subparsers):
    tail_parser = subparsers.add_parser(
        "tail", help="Show the most recent usage entries"
    )
    tail_parser.add_argument(
        "-n", "--number", type=int, default=10, help="Number of recent entries to show"
    )
    tail_parser.set_defaults(func=run_tail)


def add_select_parser(subparsers):
    select_parser = subparsers.add_parser(
        "select", help="Execute a custom SELECT query on the database"
    )
    select_parser.add_argument(
        "--query", type=str, required=True, help="Custom SQL SELECT query to execute"
    )
    select_parser.add_argument(
        "--format",
        type=str,
        choices=["table", "csv"],
        default="table",
        help="Output format",
    )
    select_parser.set_defaults(func=run_select)


def add_track_parser(subparsers):
    track_parser = subparsers.add_parser("track", help="Track a new LLM usage entry")
    track_parser.add_argument(
        "--model", type=str, required=True, help="Name of the LLM model"
    )
    track_parser.add_argument(
        "--prompt-tokens", type=int, help="Number of prompt tokens"
    )
    track_parser.add_argument(
        "--completion-tokens", type=int, help="Number of completion tokens"
    )
    track_parser.add_argument("--total-tokens", type=int, help="Total number of tokens")
    track_parser.add_argument(
        "--local-prompt-tokens",
        type=int,
        help="Number of locally counted prompt tokens",
    )
    track_parser.add_argument(
        "--local-completion-tokens",
        type=int,
        help="Number of locally counted completion tokens",
    )
    track_parser.add_argument(
        "--local-total-tokens", type=int, help="Total number of locally counted tokens"
    )
    track_parser.add_argument(
        "--cost", type=float, required=True, help="Cost of the API call"
    )
    track_parser.add_argument(
        "--execution-time",
        type=float,
        required=True,
        help="Execution time in seconds"
    )
    track_parser.add_argument(
        "--timestamp",
        type=str,
        help="Timestamp of the usage "
             "(YYYY-MM-DD HH:MM:SS, default: current time)",
    )
    track_parser.add_argument(
        "--caller-name", type=str, help="Name of the calling application"
    )
    track_parser.add_argument("--username", type=str, help="Name of the user")
    track_parser.add_argument(
        "--cached-tokens",
        type=int,
        default=0,
        help="Number of tokens retrieved from cache"
    )
    track_parser.add_argument(
        "--reasoning-tokens",
        type=int,
        default=0,
        help="Number of tokens used for model reasoning"
    )
    track_parser.set_defaults(func=run_track)


def add_limits_parser(subparsers):
    limits_parser = subparsers.add_parser(
        "limits",
        help="Manage usage limits"
    )
    limits_subparsers = limits_parser.add_subparsers(
        dest="limit_command", help="Limit commands"
    )

    # Add limit command
    add_limit_parser = limits_subparsers.add_parser(
        "add", help="Add a new usage limit"
    )
    add_limit_parser.add_argument(
        "--scope",
        type=str,
        choices=[e.value for e in LimitScope],
        required=True,
        help="Scope of the limit (global, model, user, caller)",
    )
    add_limit_parser.add_argument(
        "--limit-type",
        type=str,
        choices=[e.value for e in LimitType],
        required=True,
        help="Type of the limit (requests, input_tokens, output_tokens, cost)"
    )
    add_limit_parser.add_argument(
        "--max-value",
        type=float,
        required=True,
        help="Maximum allowed value for the limit"
    )
    add_limit_parser.add_argument(
        "--interval-unit",
        type=str,
        choices=[e.value for e in TimeInterval],
        required=True,
        help="Unit of the time interval (second, minute, hour, day, week, month)"
    )
    add_limit_parser.add_argument(
        "--interval-value",
        type=int,
        required=True,
        help="Value of the time interval"
    )
    add_limit_parser.add_argument(
        "--model", type=str, help="Model name for 'model' scope"
    )
    add_limit_parser.add_argument(
        "--username", type=str, help="Username for 'user' scope"
    )
    add_limit_parser.add_argument(
        "--caller-name", type=str, help="Caller name for 'caller' scope"
    )
    add_limit_parser.set_defaults(func=run_add_limit)

    # View limits command
    view_limits_parser = limits_subparsers.add_parser(
        "view", help="View existing usage limits"
    )
    view_limits_parser.set_defaults(func=run_view_limits)

    # Delete limit command
    delete_limit_parser = limits_subparsers.add_parser(
        "delete", help="Delete a usage limit by ID"
    )
    delete_limit_parser.add_argument(
        "--id", type=int, required=True, help="ID of the limit to delete"
    )
    delete_limit_parser.set_defaults(func=run_delete_limit)
