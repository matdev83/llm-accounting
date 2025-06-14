from datetime import datetime, timezone
from llm_accounting.audit_log import AuditLogger


def run_log_event(args, accounting):
    """Logs an audit event."""
    audit_logger: AuditLogger = accounting.audit_logger

    timestamp = None
    if args.timestamp:
        try:
            timestamp = datetime.fromisoformat(args.timestamp)
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            else:  # If it is timezone-aware, convert to UTC
                timestamp = timestamp.astimezone(timezone.utc)
        except ValueError:
            try:
                # Attempt to parse common format 'YYYY-MM-DD HH:MM:SS'
                timestamp = datetime.strptime(args.timestamp, '%Y-%m-%d %H:%M:%S')
                timestamp = timestamp.replace(tzinfo=timezone.utc)  # Assume UTC
            except ValueError:
                print(f"Error: Could not parse provided timestamp '{args.timestamp}'. Please use ISO format or 'YYYY-MM-DD HH:MM:SS'.")
                return

    try:
        audit_logger.log_event(
            app_name=args.app_name,
            user_name=args.user_name,
            model=args.model,
            log_type=args.log_type,
            prompt_text=getattr(args, 'prompt_text', None),
            response_text=getattr(args, 'response_text', None),
            remote_completion_id=getattr(args, 'remote_completion_id', None),
            project=getattr(args, 'project', None),
            timestamp=timestamp,  # Pass the parsed datetime object
            session=getattr(args, 'session', None),
        )
        print(f"Successfully logged event for app '{args.app_name}' and user '{args.user_name}'.")
    except Exception as e:
        print(f"Error logging event: {e}")
