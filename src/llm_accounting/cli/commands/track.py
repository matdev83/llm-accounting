import sys
from datetime import datetime

from llm_accounting import LLMAccounting

from ..utils import console


def run_track(args, accounting: LLMAccounting):
    """Track a new LLM usage entry"""
    timestamp = None
    if args.timestamp:
        try:
            timestamp = datetime.strptime(args.timestamp, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            console.print(
                "[red]Error: Invalid timestamp format. Use YYYY-MM-DD HH:MM:SS.[/red]"
            )
            sys.exit(1)

    accounting.track_usage(
        model=args.model,
        prompt_tokens=args.prompt_tokens,
        completion_tokens=args.completion_tokens,
        total_tokens=args.total_tokens,
        local_prompt_tokens=args.local_prompt_tokens,
        local_completion_tokens=args.local_completion_tokens,
        local_total_tokens=args.local_total_tokens,
        cost=args.cost,
        execution_time=args.execution_time,
        timestamp=timestamp,
        caller_name=args.caller_name or "",
        username=args.username or "",
        cached_tokens=args.cached_tokens,
        reasoning_tokens=args.reasoning_tokens,
    )
    console.print("[green]Usage entry tracked successfully[/green]")
