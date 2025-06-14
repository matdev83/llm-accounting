from llm_accounting.cli.commands.purge import run_purge
from llm_accounting.cli.commands.select import run_select
from llm_accounting.cli.commands.stats import run_stats
from llm_accounting.cli.commands.tail import run_tail
from llm_accounting.cli.commands.track import run_track
from llm_accounting.cli.commands.limits import set_limit, list_limits, delete_limit
from llm_accounting.models.limits import LimitScope, LimitType, TimeInterval
from llm_accounting.cli.commands.log_event import run_log_event
from llm_accounting.cli.commands.projects import (
    run_project_add,
    run_project_list,
    run_project_update,
    run_project_delete,
)
from llm_accounting.cli.commands.users import (
    run_user_add,
    run_user_list,
    run_user_update,
    run_user_deactivate,
)


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
        "select", help="Execute a custom SELECT query on the database or filter entries"
    )
    select_parser.add_argument(
        "--query", type=str, help="Custom SQL SELECT query to execute. If not provided, basic filtering will be used."
    )
    select_parser.add_argument(
        "--project",
        type=str,
        default=None,
        help="Filter usage entries by project name. Use 'NULL' to find entries with no project.",
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
    track_parser.add_argument(
        "--project",  # This is for tracking usage, distinct from --project-name for limits
        type=str,
        default=None,
        help="The project name to associate with this usage entry.",
    )
    track_parser.add_argument(
        "--session",
        type=str,
        default=None,
        help="Optional session identifier",
    )
    track_parser.set_defaults(func=run_track)


def add_limits_parser(subparsers):
    limits_parser = subparsers.add_parser(
        "limits", help="Manage usage limits (set, list, delete)"
    )
    limits_subparsers = limits_parser.add_subparsers(
        dest="limits_command", help="Limits commands", required=True  # Make subcommand required
    )

    # Set limit subparser
    set_parser = limits_subparsers.add_parser("set", help="Set a new usage limit")
    set_parser.add_argument(
        "--scope",
        type=str,
        choices=[e.value for e in LimitScope],  # LimitScope enum now includes PROJECT
        required=True,
        help="Scope of the limit (GLOBAL, MODEL, USER, CALLER, PROJECT)",
    )
    set_parser.add_argument(
        "--limit-type",
        type=str,
        choices=[e.value for e in LimitType],
        required=True,
        help="Type of the limit (requests, input_tokens, output_tokens, total_tokens, cost)",
    )
    set_parser.add_argument(
        "--max-value",
        type=float,
        required=True,
        help="Maximum value for the limit. Use 0 to deny usage, -1 for unlimited",
    )
    set_parser.add_argument(
        "--interval-unit",
        type=str,
        choices=[e.value for e in TimeInterval],
        required=True,
        help="Unit of the time interval (second, minute, hour, day, week, monthly)",
    )
    set_parser.add_argument(
        "--interval-value",
        type=int,
        required=True,
        help="Value of the time interval (e.g., 1 for '1 day')",
    )
    set_parser.add_argument(
        "--model",
        type=str,
        help="Model name for MODEL scope limits (use '*' as wildcard). Can be combined with PROJECT scope.",
    )
    set_parser.add_argument(
        "--username",
        type=str,
        help="Username for USER scope limits (use '*' as wildcard). Can be combined with PROJECT scope.",
    )
    set_parser.add_argument(
        "--caller-name",
        type=str,
        help="Caller name for CALLER scope limits (use '*' as wildcard). Can be combined with PROJECT scope.",
    )
    set_parser.add_argument(
        "--project-name",
        type=str,
        help="The project name for a PROJECT-specific limit (use '*' as wildcard). Required if scope is PROJECT.",
    )
    set_parser.set_defaults(func=set_limit)

    # List limits subparser
    list_parser = limits_subparsers.add_parser("list", help="List all usage limits")
    # Add arguments to filter list by scope, model, username, caller_name, project_name
    list_parser.add_argument(
        "--scope", type=str, choices=[e.value for e in LimitScope], help="Filter by scope."
    )
    list_parser.add_argument(
        "--model", type=str, help="Filter by model name."
    )
    list_parser.add_argument(
        "--username", type=str, help="Filter by username."
    )
    list_parser.add_argument(
        "--caller-name", type=str, help="Filter by caller name."
    )
    list_parser.add_argument(
        "--project-name", type=str, help="Filter by project name."
    )
    list_parser.set_defaults(func=list_limits)

    # Delete limit subparser
    delete_parser = limits_subparsers.add_parser("delete", help="Delete a usage limit")
    delete_parser.add_argument(
        "--id", type=int, required=True, help="ID of the limit to delete"
    )
    delete_parser.set_defaults(func=delete_limit)


def add_log_event_parser(subparsers):
    """Adds the parser for the log-event command."""
    parser = subparsers.add_parser("log-event", help="Log an audit event")
    parser.add_argument("--app-name", type=str, required=True, help="Name of the application")
    parser.add_argument("--user-name", type=str, required=True, help="Name of the user")
    parser.add_argument("--model", type=str, required=True, help="Name of the model used")
    parser.add_argument("--log-type", type=str, required=True, help="Type of log event (e.g., 'completion', 'feedback')")
    parser.add_argument("--prompt-text", type=str, help="Text of the prompt")
    parser.add_argument("--response-text", type=str, help="Text of the response")
    parser.add_argument("--remote-completion-id", type=str, help="Remote ID of the completion")
    parser.add_argument("--project", type=str, help="Project associated with the event")
    parser.add_argument("--timestamp", type=str, help="Timestamp of the event (YYYY-MM-DD HH:MM:SS or ISO format, default: current time)")
    parser.add_argument("--session", type=str, help="Optional session identifier")
    parser.set_defaults(func=run_log_event)


def add_projects_parser(subparsers):
    parser = subparsers.add_parser("projects", help="Manage allowed projects")
    proj_sub = parser.add_subparsers(dest="projects_command", required=True)

    add_p = proj_sub.add_parser("add", help="Add a new project")
    add_p.add_argument("name", type=str)
    add_p.set_defaults(func=run_project_add)

    list_p = proj_sub.add_parser("list", help="List projects")
    list_p.set_defaults(func=run_project_list)

    upd_p = proj_sub.add_parser("update", help="Rename a project")
    upd_p.add_argument("name", type=str)
    upd_p.add_argument("new_name", type=str)
    upd_p.set_defaults(func=run_project_update)

    del_p = proj_sub.add_parser("delete", help="Delete a project")
    del_p.add_argument("name", type=str)
    del_p.set_defaults(func=run_project_delete)


def add_users_parser(subparsers):
    parser = subparsers.add_parser("users", help="Manage allowed users")
    user_sub = parser.add_subparsers(dest="users_command", required=True)

    add_u = user_sub.add_parser("add", help="Add a new user")
    add_u.add_argument("user_name", type=str)
    add_u.add_argument("--ou-name", type=str, default=None)
    add_u.add_argument("--email", type=str, default=None)
    add_u.set_defaults(func=run_user_add)

    list_u = user_sub.add_parser("list", help="List users")
    list_u.set_defaults(func=run_user_list)

    upd_u = user_sub.add_parser("update", help="Update a user")
    upd_u.add_argument("user_name", type=str)
    upd_u.add_argument("--new-user-name", type=str, default=None)
    upd_u.add_argument("--ou-name", type=str, default=None)
    upd_u.add_argument("--email", type=str, default=None)
    upd_u.set_defaults(func=run_user_update)

    deact_u = user_sub.add_parser("deactivate", help="Deactivate a user")
    deact_u.add_argument("user_name", type=str)
    deact_u.set_defaults(func=run_user_deactivate)
