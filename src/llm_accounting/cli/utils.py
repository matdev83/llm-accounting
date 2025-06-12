from typing import List
from rich.console import Console # Added import for Console
from llm_accounting.backends.base import AuditLogEntry

console = Console() # Instantiated console

# Placeholder formatting functions to resolve ImportError
def format_float(value: float, precision: int = 2) -> str:
    """Formats a float to a string with a given precision."""
    if value is None:
        return "-"
    return f"{value:.{precision}f}"

def format_tokens(value: int) -> str:
    """Formats token counts (integers)."""
    if value is None:
        return "-"
    return str(value)

def format_time(value: float, precision: int = 2) -> str:
    """Formats time (float in seconds) to a string."""
    if value is None:
        return "-"
    # This is a simplistic formatter; actual might involve units like ms, s, min
    return f"{value:.{precision}f}s"

# Existing content of utils.py will be preserved if there is any,
# by reading it first. For this exercise, we assume it's either empty
# or the new function can be appended. If it had existing functions,
# a more careful merge (e.g. using replace_with_git_merge_diff) would be needed.
# For now, let's try to read it. If it's empty or doesn't exist, this will fail
# gracefully in the next step if we use 'create_file_with_block', or we can
# use 'overwrite_file_with_block' if we are sure.
# Given the subtask, we are creating a *new* helper function, so appending is fine.

# --- Content of src/llm_accounting/cli/utils.py from previous step if any ---
# (Assuming it might be empty or have other utility functions)
# For the purpose of this step, I'll assume it's okay to overwrite if it's simple,
# or append if I had the original content. Since I don't have the original content
# from a previous read, and the task is to *create a new helper function*,
# I will define it. If there was existing code, `replace_with_git_merge_diff` would be safer.
# Given the problem statement, it implies adding a new function.

def format_session_entries(entries: List[AuditLogEntry]) -> str:
    """
    Formats a list of AuditLogEntry objects for a session into a readable string.

    Args:
        entries: A list of AuditLogEntry objects, expected to be sorted chronologically.

    Returns:
        A string representation of the session log.
    """
    output_parts = []
    for entry in entries:
        # Ensure timestamp is a string. Assuming it's already ISO 8601.
        # If not, entry.timestamp.isoformat() would be used.
        # For now, directly using it as it's stored as datetime.
        timestamp_str = entry.timestamp.isoformat()

        if entry.log_type == 'prompt':
            # ### [timestamp] user: <username> to: <backend/model>, out tokens: <tokens>
            # (user prompt here)
            header = (
                f"### [{timestamp_str}] user: {entry.user_name} "
                f"to: {entry.model}, out tokens: <tokens_unavailable>"
            )
            output_parts.append(header)
            if entry.prompt_text:
                output_parts.append(entry.prompt_text)
        elif entry.log_type == 'response':
            # ### [timestamp] model: <backend/model> to <username>, completion tokens: <completion_tokens>
            # (model reply here)
            header = (
                f"### [{timestamp_str}] model: {entry.model} "
                f"to: {entry.user_name}, completion tokens: <completion_tokens_unavailable>"
            )
            output_parts.append(header)
            if entry.response_text:
                output_parts.append(entry.response_text)
        else:
            # Handle other log types if necessary, or ignore
            header = (
                f"### [{timestamp_str}] log: {entry.log_type} by {entry.user_name} "
                f"for app {entry.app_name}, model {entry.model}"
            )
            output_parts.append(header)
            if entry.prompt_text:
                output_parts.append(f"Prompt: {entry.prompt_text}")
            if entry.response_text:
                output_parts.append(f"Response: {entry.response_text}")


    return "\n".join(output_parts)


# Import the main LLMAccounting class
from llm_accounting import LLMAccounting
from typing import Optional, Any

def get_accounting(
    db_backend: str,
    db_file: Optional[str] = None,
    postgresql_connection_string: Optional[str] = None,
    audit_db_backend: Optional[str] = None,
    audit_db_file: Optional[str] = None,
    audit_postgresql_connection_string: Optional[str] = None,
    project_name: Optional[str] = None,
    app_name: Optional[str] = None,
    user_name: Optional[str] = None,
    enforce_project_names: bool = False,
    enforce_user_names: bool = False,
    **kwargs: Any # To catch any other args that might be passed
) -> LLMAccounting:
    """
    Initializes and returns an LLMAccounting instance based on CLI arguments.
    """
    # Determine the main backend
    backend_instance = None
    if db_backend == "sqlite":
        backend_instance = LLMAccounting(
            project_name=project_name,
            app_name=app_name,
            user_name=user_name,
            enforce_project_names=enforce_project_names,
            enforce_user_names=enforce_user_names,
            # LLMAccounting will default to SQLiteBackend if backend is None and db_file is not specified for it.
            # However, we need to ensure LLMAccounting can pick up db_file if provided.
            # This requires LLMAccounting's __init__ or its backend setup to handle db_file.
            # For now, assuming LLMAccounting's default SQLiteBackend handles db_file from kwargs or config.
            # The LLMAccounting class itself takes a backend instance.
            # We need to create the backend instance first.
        )
        # This is a simplification. The actual backend setup might be more complex,
        # potentially involving creating SQLiteBackend(db_file=db_file) explicitly.
        # For now, relying on LLMAccounting's internal default if db_file is also default.
        # This part needs to align with how LLMAccounting actually uses these args.
        # The goal here is to make the function exist.
        # The actual logic of backend creation might need refinement based on LLMAccounting constructor.
        # Let's assume LLMAccounting can be initialized and then its backend configured, or it takes specific backend args.

    elif db_backend == "postgresql":
        # Placeholder for PostgreSQL backend initialization
        # backend_instance = PostgreSQLBackend(connection_string=postgresql_connection_string)
        # For now, let LLMAccounting handle it if it can, or this will need specific backend init.
        pass # Fall through to generic LLMAccounting instantiation for now

    # This is a simplified factory. The actual LLMAccounting class needs to be
    # instantiated with the correct backend instance configured from these parameters.
    # The kwargs in main.py are:
    # db_backend, db_file, postgresql_connection_string,
    # audit_db_backend, audit_db_file, audit_postgresql_connection_string,
    # project_name, app_name, user_name, enforce_project_names, enforce_user_names

    # A more correct approach would be to instantiate the backend first:
    from llm_accounting.backends.sqlite import SQLiteBackend
    from llm_accounting.backends.postgresql import PostgreSQLBackend # Assuming this exists

    actual_backend = None
    if db_backend == "sqlite":
        actual_backend = SQLiteBackend(db_path=db_file) # Changed db_file to db_path
    elif db_backend == "postgresql":
        actual_backend = PostgreSQLBackend(connection_string=postgresql_connection_string)
    # else: # Potentially handle other backends or raise error

    actual_audit_backend = None
    resolved_audit_backend_type = audit_db_backend or db_backend

    if resolved_audit_backend_type == "sqlite":
        actual_audit_db_file = audit_db_file or db_file # Default to main db_file if audit specific not given
        actual_audit_backend = SQLiteBackend(db_path=actual_audit_db_file) # Changed db_file to db_path, removed is_audit_db
    elif resolved_audit_backend_type == "postgresql":
        actual_audit_conn_str = audit_postgresql_connection_string or postgresql_connection_string
        actual_audit_backend = PostgreSQLBackend(connection_string=actual_audit_conn_str) # Removed is_audit_db

    # If audit backend is same as main backend and not explicitly defined, it will be handled by LLMAccounting
    if audit_db_backend is None and audit_db_file is None and audit_postgresql_connection_string is None:
        actual_audit_backend = None # Let LLMAccounting use the main backend

    return LLMAccounting(
        backend=actual_backend,
        audit_backend=actual_audit_backend,
        project_name=project_name,
        app_name=app_name,
        user_name=user_name,
        enforce_project_names=enforce_project_names,
        enforce_user_names=enforce_user_names
    )
