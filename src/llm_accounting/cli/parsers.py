from llm_accounting.cli.commands.purge import run_purge
from llm_accounting.cli.commands.select import run_select
from llm_accounting.cli.commands.stats import run_stats
from llm_accounting.cli.commands.tail import run_tail
from llm_accounting.cli.commands.track import run_track


def add_stats_parser(subparsers):
    stats_parser = subparsers.add_parser("stats", help="Show usage statistics")
    stats_parser.add_argument(
        "--period",
        type=str,
        choices=["daily", "weekly", "monthly", "yearly"],
        help="Show stats for a specific period (daily, weekly, monthly, or yearly)",
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
        "--execution-time", type=float, required=True, help="Execution time in seconds"
    )
    track_parser.add_argument(
        "--timestamp",
        type=str,
        help="Timestamp of the usage (YYYY-MM-DD HH:MM:SS, default: current time)",
    )
    track_parser.add_argument(
        "--caller-name", type=str, help="Name of the calling application"
    )
    track_parser.add_argument("--username", type=str, help="Name of the user")
    track_parser.add_argument(
        "--cached-tokens",
        type=int,
        default=0,
        help="Number of tokens retrieved from cache",
    )
    track_parser.add_argument(
        "--reasoning-tokens",
        type=int,
        default=0,
        help="Number of tokens used for model reasoning",
    )
    track_parser.set_defaults(func=run_track)
