import sys
# Assuming 'accounting' object passed to handle_session_command has 'audit_logger'
# from llm_accounting.audit_log import AuditLogger # Not strictly needed if type hinting 'accounting'
from llm_accounting.cli.utils import format_session_entries
# For type hinting `args` if needed, you'd import argparse.Namespace
# from argparse import Namespace
# For type hinting `accounting` which holds `audit_logger`
# from llm_accounting.config import AppConfig # Or wherever AppConfig is defined that holds audit_logger

def handle_session_command(args, accounting) -> None:
    """
    Handles the 'session' command.
    Retrieves and displays audit log entries for a specific session ID.

    Args:
        args: Parsed command-line arguments (should have a 'session_id' attribute).
        accounting: The main accounting application object, expected to have an 'audit_logger'.
    """
    audit_logger = accounting.audit_logger

    try:
        session_entries = audit_logger.get_session_entries(args.session_id)
        if not session_entries: # Should be caught by ValueError in get_session_entries, but as a safeguard
            print(f"No audit log entries found for session ID: {args.session_id}")
            sys.exit(0) # Not an error, just no data. Or could be an error, depending on desired UX.
                        # The spec says get_session_entries raises ValueError, so this path might not be hit.

        formatted_output = format_session_entries(session_entries)
        print(formatted_output)
    except ValueError as e:
        # Assuming ValueError is raised by get_session_entries for not found
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        # Catch any other unexpected errors
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)
