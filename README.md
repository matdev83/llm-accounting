# LLM Accounting

A Python package for tracking and analyzing LLM usage across different models and applications. It is primarily designed as a library for integration into development process of LLM-based agentic workflow tooling, providing robust tracking capabilities. While its main use is as a library, it also provides a powerful CLI for scripting and batch workloads.

**Keywords**: LLM, accounting, usage tracking, cost management, token counting, agentic workflows, AI, Python

## Features

- Track usage of different LLM models
- Track usage by project
- Record token counts (prompt, completion, total)
- Track costs and execution times
- Support for local token counting
- Pluggable backend system (SQLite, PostgreSQL, and CSV file-based backends supported)
- CLI interface for viewing and tracking usage statistics
- Support for tracking caller application and username
- Automatic database schema migration (for supported backends)
- Strict model name validation
- Automatic timestamp handling
- Comprehensive audit logging for all LLM interactions

## Installation

```bash
pip install llm-accounting
```

For specific database backends, install the corresponding optional dependencies:

```bash
# For SQLite (default)
pip install llm-accounting[sqlite]

# For PostgreSQL
pip install llm-accounting[postgresql]

# CSV backend uses standard Python modules and requires no extra dependencies.
```

## Usage

### Basic Usage

The `LLMAccounting` class automatically manages the database connection for its chosen backend. You can simply instantiate it and call its methods; the backend will ensure the connection is active when needed.

```python
from llm_accounting import LLMAccounting
from datetime import datetime, timedelta

# Default backend (SQLite) is used if no backend is provided
# You can also set default project, app, and user names here
accounting = LLMAccounting(
    project_name="my_default_project", # Optional: default project for all entries
    app_name="my_default_app",         # Optional: default caller name for all entries
    user_name="my_default_user"        # Optional: default username for all entries
)

# Track usage (model name is required, timestamp is optional)
# Parameters provided here will override the defaults set in the constructor
accounting.track_usage(
    model="gpt-4",  # Required: name of the LLM model
    prompt_tokens=100,
    completion_tokens=50,
    total_tokens=150,
    cost=0.002,
    execution_time=1.5,
    caller_name="my_app",  # Optional: name of the calling application (overrides default app_name)
    username="john_doe",   # Optional: name of the user (overrides default user_name)
    project="my_project",  # Optional: name of the project (overrides default project_name)
    timestamp=None         # Optional: if None, current time will be used
)

# Get statistics
end_date = datetime.now()
start_date = end_date - timedelta(days=7) # Last 7 days
stats = accounting.get_period_stats(start_date, end_date)
model_stats = accounting.get_model_stats(start_date, end_date)
rankings = accounting.get_model_rankings(start_date, end_date)

print(f"Total cost last 7 days: {stats.sum_cost}")
print(f"Model stats: {model_stats}")
print(f"Model rankings: {rankings}")

# When you are done with the accounting instance, it's good practice to close it.
# If used as a context manager, it will be closed automatically.
accounting.close()
```
*Note: The `LLMAccounting` class and its methods are synchronous. If you are integrating `llm-accounting` into an asynchronous application, you should run its synchronous calls in a separate thread (e.g., using `asyncio.to_thread`) to avoid blocking the event loop.*

### CLI Usage

#### Global CLI Options

The following options can be used with any `llm-accounting` command:

*   `--db-file <path>`: Specifies the SQLite database file path. Only applicable when `--db-backend` is `sqlite`.
*   `--db-backend <backend>`: Selects the database backend (`sqlite`, `postgresql`, or `csv`). Defaults to `sqlite`.
*   `--csv-data-dir <path>`: Specifies the directory for CSV data files (e.g., `accounting_entries.csv`). Only applicable when `--db-backend` is `csv`. Defaults to `data/`.
*   `--postgresql-connection-string <string>`: Connection string for the PostgreSQL database. Required when `--db-backend` is `postgresql`. Can also be provided via `POSTGRESQL_CONNECTION_STRING` environment variable.
*   `--project-name <name>`: Default project name to associate with usage entries. Can be overridden by command-specific `--project`.
*   `--app-name <name>`: Default application name to associate with usage entries. Can be overridden by command-specific `--caller-name`.
*   `--user-name <name>`: Default user name to associate with usage entries. Can be overridden by command-specific `--username`. Defaults to current system user.

```bash
# Track a new usage entry (model name is required, timestamp is optional)
llm-accounting track \
    --model gpt-4 \
    --prompt-tokens 100 \
    --completion-tokens 50 \
    --total-tokens 150 \
    --cost 0.002 \
    --execution-time 1.5 \
    --caller-name my_app \
    --username john_doe \
    --project my_project \
    --timestamp "2024-01-01T12:00:00" \
    --cached-tokens 20 \
    --reasoning-tokens 10
```

#### `log-event` Command

Logs a generic event to the audit log. This is useful for recording custom events, feedback, or other notable occurrences related to LLM interactions that might not fit the standard usage tracking.

**Arguments:**

*   `--app-name` (string, required): Name of the application.
*   `--user-name` (string, required): Name of the user.
*   `--model` (string, required): Name of the LLM model associated with the event.
*   `--log-type` (string, required): Type of the log entry (e.g., 'info', 'warning', 'error', 'feedback', or a custom type).
*   `--prompt-text` (string, optional): Text of the prompt, if relevant.
*   `--response-text` (string, optional): Text of the response, if relevant.
*   `--remote-completion-id` (string, optional): ID of the remote completion, if relevant.
*   `--project` (string, optional): Project name to associate with the event.
*   `--timestamp` (string, optional): Timestamp of the event (YYYY-MM-DD HH:MM:SS or ISO format, e.g., "2023-10-27T14:30:00Z". Defaults to current time).

**Example:**

```bash
llm-accounting log-event \
    --app-name my-app \
    --user-name testuser \
    --model gpt-4 \
    --log-type info \
    --prompt-text "User reported positive feedback." \
    --project "Alpha" \
    --timestamp "2024-01-15T10:30:00"
```

```bash
# Show today's stats
llm-accounting stats --daily

# Show stats for a custom period
llm-accounting stats --start 2024-01-01 --end 2024-01-31

# Show most recent entries
llm-accounting tail

# Show last 5 entries
llm-accounting tail -n 5

# Delete all entries
llm-accounting purge

# Execute custom SQL queries (if backend supports it and it's enabled)
llm-accounting select --query "SELECT model, COUNT(*) as count FROM accounting_entries GROUP BY model"
```

### Usage Limits

The `llm-accounting limits` command allows you to manage usage limits for your LLM interactions. You can set, list, and delete limits based on various scopes (global, model, user, caller) and types (requests, input tokens, output tokens, cost) over specified time intervals.

#### Set a Usage Limit

Set a new usage limit. For example, to set a global limit of 1000 requests per day:

```bash
llm-accounting limits set \
    --scope GLOBAL \
    --limit-type requests \
    --max-value 1000 \
    --interval-unit day \
    --interval-value 1
```

To set a cost limit of $5.00 per hour for a specific user:

```bash
llm-accounting limits set \
    --scope USER \
    --username john_doe \
    --limit-type cost \
    --max-value 5.00 \
    --interval-unit hour \
    --interval-value 1
```

To set an input token limit of 50000 tokens per week for a specific model:

```bash
llm-accounting limits set \
    --scope MODEL \
    --model gpt-4 \
    --limit-type input_tokens \
    --max-value 50000 \
    --interval-unit week \
    --interval-value 1
```

To set a cost limit of $10.00 per day for a specific project:

```bash
llm-accounting limits set \
    --scope PROJECT \
    --project my_project \
    --limit-type cost \
    --max-value 10.00 \
    --interval-unit day \
    --interval-value 1
```

#### List Usage Limits

List all configured usage limits:

```bash
llm-accounting limits list
```

#### Delete a Usage Limit

Delete a usage limit by its ID (you can find the ID using `llm-accounting limits list`):

```bash
llm-accounting limits delete --id 1
```

### Database Backend Selection via CLI

You can specify the database backend directly via the CLI using the `--db-backend` option. This allows you to switch between `sqlite` (default) and `postgresql` without modifying code.

```bash
# Use SQLite backend (default behavior, --db-backend can be omitted)
llm-accounting --db-backend sqlite --db-file my_sqlite_db.sqlite stats --daily

# Use PostgreSQL backend
# Requires POSTGRESQL_CONNECTION_STRING environment variable to be set, or provide it directly
llm-accounting --db-backend postgresql --postgresql-connection-string "postgresql://user:pass@localhost:5432/mydatabase" stats --daily

# Example: Track usage with PostgreSQL backend
llm-accounting --db-backend postgresql \
    --postgresql-connection-string "postgresql://user:pass@localhost:5432/mydatabase" \
    track \
    --model gpt-4 \
    --prompt-tokens 10 \
    --cost 0.0001

# Example: Get daily stats using CSV backend with a custom data directory
llm-accounting --db-backend csv --csv-data-dir /path/to/my/csvs stats --daily
```

### Shell Script Integration

The CLI can be easily integrated into shell scripts. Here's an example:

```bash
#!/bin/bash

# Track usage after an LLM API call
llm-accounting track \
    --model "gpt-4" \
    --prompt-tokens "$PROMPT_TOKENS" \
    --completion-tokens "$COMPLETION_TOKENS" \
    --total-tokens "$TOTAL_TOKENS" \
    --cost "$COST" \
    --execution-time "$EXECUTION_TIME" \
    --caller-name "my_script" \
    --username "$USER"

# Check daily usage
llm-accounting stats --daily
```

## Database Schema

The database schema generally includes the following tables and key fields (specifics might vary slightly by backend, but `PostgreSQLBackend` adheres to this structure):

**`accounting_entries` Table:**
- `id`: SERIAL PRIMARY KEY - Unique identifier for the entry.
- `model_name`: VARCHAR(255) NOT NULL - Name of the LLM model.
- `prompt_tokens`: INTEGER - Number of tokens in the prompt.
- `completion_tokens`: INTEGER - Number of tokens in the completion.
- `total_tokens`: INTEGER - Total tokens (prompt + completion).
- `local_prompt_tokens`: INTEGER - Locally counted prompt tokens.
- `local_completion_tokens`: INTEGER - Locally counted completion tokens.
- `local_total_tokens`: INTEGER - Total locally counted tokens.
- `cost`: DOUBLE PRECISION NOT NULL - Cost of the API call.
- `execution_time`: DOUBLE PRECISION - Execution time in seconds.
- `timestamp`: TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP - Timestamp of the usage.
- `caller_name`: VARCHAR(255) - Optional identifier for the calling application/script.
- `username`: VARCHAR(255) - Optional identifier for the user.
- `project_name`: VARCHAR(255) - Optional identifier for the project.
- `cached_tokens`: INTEGER - Number of tokens retrieved from cache.
- `reasoning_tokens`: INTEGER - Number of tokens used for model reasoning/tool use.

**`usage_limits` Table (for defining quotas/limits):**
- `id`: SERIAL PRIMARY KEY
- `scope`: VARCHAR(50) NOT NULL (e.g., 'USER', 'GLOBAL')
- `limit_type`: VARCHAR(50) NOT NULL (e.g., 'COST', 'REQUESTS')
- `max_value`: DOUBLE PRECISION NOT NULL
- `interval_unit`: VARCHAR(50) NOT NULL (e.g., 'HOURLY', 'DAILY')
- `interval_value`: INTEGER NOT NULL
- `model_name`: VARCHAR(255) (Optional, for model-specific limits)
- `username`: VARCHAR(255) (Optional, for user-specific limits)
- `caller_name`: VARCHAR(255) (Optional, for caller-specific limits)
- `created_at`: TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
- `updated_at`: TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP

**`audit_log_entries` Table (for detailed event logging):**
- `id`: SERIAL PRIMARY KEY
- `timestamp`: TIMESTAMPTZ NOT NULL
- `app_name`: VARCHAR(255) NOT NULL
- `user_name`: VARCHAR(255) NOT NULL
- `model`: VARCHAR(255) NOT NULL
- `prompt_text`: TEXT
- `response_text`: TEXT
- `remote_completion_id`: VARCHAR(255)
- `project`: VARCHAR(255)
- `log_type`: TEXT NOT NULL (e.g., 'prompt', 'response', 'event')

*Note: The `id` fields are managed internally by the database.*

## Database Migrations

This project uses [Alembic](https://alembic.sqlalchemy.org/) to manage database schema migrations, working in conjunction with our SQLAlchemy models (defined in `src/llm_accounting/models/`). While SQLAlchemy defines the desired schema, Alembic is used to generate and apply the necessary database changes.

When you make changes to the SQLAlchemy models that require a schema alteration (e.g., adding a table, adding a column, changing a column type), you need to generate a new migration script using Alembic.

### Generating a New Migration

1.  **Ensure your development database is accessible and reflects the schema *before* your new model changes.** Alembic compares your models against the live database (specifically, the state recorded in its `alembic_version` table) to generate the migration. It's usually best to have your database upgraded to the latest revision before generating a new one.
2.  **Make your changes to the SQLAlchemy models** in the `src/llm_accounting/models/` directory.
3.  **Run the following command from the project root:**

    ```bash
    LLM_ACCOUNTING_DB_URL="your_database_connection_string" alembic revision -m "descriptive_migration_name" --autogenerate
    ```

    *   Replace `"your_database_connection_string"` with the actual connection string for your development database.
        *   For SQLite (default development): `sqlite:///./data/accounting.sqlite`
        *   For PostgreSQL: `postgresql://user:pass@host:port/dbname` (use your actual credentials and host)
    *   Replace `"descriptive_migration_name"` with a short, meaningful description of the changes (e.g., `add_user_email_column`, `create_indexes_for_timestamps`). This becomes part of the migration filename.

4.  **Review the generated migration script** in the `alembic/versions/` directory. Ensure it accurately reflects the intended changes. You might need to adjust it, especially for complex changes not perfectly detected by autogenerate (e.g., specific index types, constraints, or data migrations).
5.  Commit the new migration script along with your model changes.

### Applying Migrations

Database migrations are automatically applied when the `LLMAccounting` service starts (specifically, when an `LLMAccounting` instance is created). The application will check for any pending migrations and attempt to upgrade the database to the latest version using Alembic.

## Backend Configuration

### SQLite (Default)

The default backend is SQLite, which stores data in a local file. Below is a comprehensive example demonstrating how to configure a custom SQLite database file, track usage, set and check usage limits, and utilize the audit logger.

```python
import os
from llm_accounting import LLMAccounting
from llm_accounting.backends.sqlite import SQLiteBackend
from llm_accounting.models.limits import LimitScope, LimitType, TimeInterval
import time
from datetime import datetime, timedelta
from llm_accounting.audit_log import AuditLogger

# Define custom database filenames
custom_accounting_db_filename = "my_custom_accounting.sqlite"
custom_audit_db_filename = "my_custom_audit.sqlite"

print(f"Initializing LLMAccounting with custom DB: {custom_accounting_db_filename}")

# 1. Initialize SQLiteBackend with the custom filename
sqlite_backend = SQLiteBackend(db_path=custom_accounting_db_filename)

# 2. Pass the custom backend to LLMAccounting
# The backend will automatically manage its connection.
accounting = LLMAccounting(backend=sqlite_backend)
print(f"LLMAccounting initialized. Actual DB path: {accounting.get_db_path()}")

# Example usage: track some usage
accounting.track_usage(
    model="gpt-4",
    prompt_tokens=100,
    completion_tokens=50,
    cost=0.01,
    username="example_user",
    caller_name="example_app"
)
print("Usage tracked successfully.")

# Verify stats (optional)
end_time = datetime.now()
start_time = end_time - timedelta(days=1)
stats = accounting.get_period_stats(start_time, end_time)
print(f"Stats for last 24 hours: {stats.sum_cost:.4f} cost, {stats.sum_total_tokens} tokens")

print("\n--- Testing Usage Limits ---")
# Set a global limit: 10 requests per minute
print("Setting a global limit: 10 requests per minute...")
accounting.set_usage_limit(
    scope=LimitScope.GLOBAL,
    limit_type=LimitType.REQUESTS,
    max_value=10,
    interval_unit=TimeInterval.MINUTE,
    interval_value=1
)
print("Global limit set.")

# Simulate requests and check quota
for i in range(1, 15): # Try 14 requests to exceed the limit
    model = "gpt-3.5-turbo"
    username = "test_user"
    caller_name = "test_app"
    input_tokens = 10

    allowed, reason = accounting.check_quota(
        model=model,
        username=username,
        caller_name=caller_name,
        input_tokens=input_tokens
    )
    if allowed:
        print(f"Request {i}: ALLOWED. Tracking usage...")
        accounting.track_usage(
            model=model,
            prompt_tokens=input_tokens,
            cost=0.0001,
            username=username,
            caller_name=caller_name
        )
    else:
        print(f"Request {i}: DENIED. Reason: {reason}")
    
    # Small delay to simulate real-world requests, but not enough to reset minute limit
    time.sleep(0.1) 

# It's good practice to explicitly close the accounting instance when done,
# though the backend methods will auto-connect if needed for subsequent calls.
accounting.close()

print(f"\nInitializing AuditLogger with custom DB: {custom_audit_db_filename}")

# Initialize AuditLogger with the custom filename
with AuditLogger(db_path=custom_audit_db_filename) as audit_logger:
    print(f"AuditLogger initialized. Actual DB path: {audit_logger.get_db_path()}")

    # Example usage: log a prompt
    audit_logger.log_prompt(
        app_name="my_app",
        user_name="test_user",
        model="gpt-3.5-turbo",
        prompt_text="Hello, how are you?"
    )
    print("Prompt logged successfully.")

    # Example usage: log a response
    audit_logger.log_response(
        app_name="my_app",
        user_name="test_user",
        model="gpt-3.5-turbo",
        response_text="I am doing well, thank you!",
        remote_completion_id="comp_123"
    )
    print("Response logged successfully.")

    # Example usage: get audit log entries
    print("\nRetrieving audit log entries...")
    entries = audit_logger.get_entries(limit=5)
    for entry in entries:
        print(f"  [{entry.timestamp}] App: {entry.app_name}, User: {entry.user_name}, Model: {entry.model}, Type: {entry.log_type}")
        if entry.prompt_text:
            print(f"    Prompt: {entry.prompt_text[:50]}...")
        if entry.response_text:
            print(f"    Response: {entry.response_text[:50]}...")
    print(f"Retrieved {len(entries)} audit log entries.")

# Clean up the created database files (for example purposes)
print("\nCleaning up created database files...")
if os.path.exists(custom_accounting_db_filename):
    os.remove(custom_accounting_db_filename)
    print(f"Removed {custom_accounting_db_filename}")
if os.path.exists(custom_audit_db_filename):
    os.remove(custom_audit_db_filename)
    print(f"Removed {custom_audit_db_filename}")

print("\nExample complete.")
```

### CSV Backend

The `CSVBackend` provides a simple, file-based way to store and manage LLM usage data without requiring a database server. It's suitable for local analysis, smaller projects, or when a quick setup is needed.

**Characteristics:**

*   **Data Storage**: Stores data in plain CSV files.
*   **Default Directory**: Uses `data/` in the current working directory by default. This can be configured using the `--csv-data-dir` CLI option or the `csv_data_dir` parameter when instantiating `CSVBackend`.
*   **Files Created**:
    *   `accounting_entries.csv`: Stores detailed LLM usage records.
    *   `usage_limits.csv`: Stores defined usage limits.
    *   `audit_log_entries.csv`: Stores audit log events.
*   **Schema/Columns**:
    *   **`accounting_entries.csv`**: `id, model, prompt_tokens, completion_tokens, total_tokens, local_prompt_tokens, local_completion_tokens, local_total_tokens, cost, execution_time, timestamp, caller_name, username, project, cached_tokens, reasoning_tokens`
    *   **`usage_limits.csv`**: `id, scope, limit_type, model, username, caller_name, project_name, max_value, interval_unit, interval_value, created_at, updated_at`
    *   **`audit_log_entries.csv`**: `id, timestamp, app_name, user_name, model, prompt_text, response_text, remote_completion_id, project, log_type`

**Python Usage Example:**

```python
from llm_accounting import LLMAccounting
from llm_accounting.backends.csv_backend import CSVBackend
from datetime import datetime, timedelta

# Initialize CSVBackend, optionally specify data directory
csv_backend = CSVBackend(csv_data_dir="my_csv_data") 
accounting = LLMAccounting(backend=csv_backend)

# Use accounting as usual
accounting.track_usage(model="test-csv-model", prompt_tokens=20, cost=0.002)
print("Usage tracked with CSV backend.")

end_date = datetime.now()
start_date = end_date - timedelta(days=1)
stats = accounting.get_period_stats(start_date, end_date)
print(f"Stats from CSV backend: Total cost: {stats.sum_cost}, Total tokens: {stats.sum_total_tokens}")

accounting.close() # No-op for CSVBackend but good practice
```

**CLI Usage Examples:**

```bash
# Track usage using CSV backend with default data directory (data/)
llm-accounting --db-backend csv track --model my-csv-model --prompt-tokens 100 --cost 0.01

# Get daily stats using CSV backend with a custom data directory
llm-accounting --db-backend csv --csv-data-dir ./my_csv_files/ stats --daily
```

### PostgreSQL Backend

The `PostgreSQLBackend` provides a reference implementation for using a PostgreSQL database with `llm-accounting`. It can be used with any standard PostgreSQL instance, including locally deployed ones, or with hosted/cloud PostgreSQL instances like [Neon](https://neon.tech/).

**1. Set Up Your PostgreSQL Database (User's Responsibility):**

To use `PostgreSQLBackend`, you'll need access to a PostgreSQL database instance. This can be:

*   **A local PostgreSQL server**: Install PostgreSQL on your machine and create a database.
*   **A hosted PostgreSQL service**: Use a cloud provider like Neon, AWS RDS, Google Cloud SQL, Azure Database for PostgreSQL, etc.

Once you have a database, obtain its connection string (URI format). It will look something like this:
    ```
    postgresql://<user>:<password>@<host>:<port>/<dbname>
    ```
    For cloud services like Neon, `sslmode=require` might be necessary:
    ```
    postgresql://<user>:<password>@<host>.neon.tech:<port>/<dbname>?sslmode=require
    ```

**2. Install Dependencies:**

The `PostgreSQLBackend` requires the `psycopg2-binary` package to communicate with PostgreSQL databases. You can install it as an extra dependency:

```bash
pip install llm-accounting[postgresql]
```

**3. Configuration:**

The `PostgreSQLBackend` primarily expects the database connection string to be available via the `POSTGRESQL_CONNECTION_STRING` environment variable.

```bash
export POSTGRESQL_CONNECTION_STRING="postgresql://your_user:your_password@your_host:5432/your_dbname"
```

Replace the placeholder values with your actual PostgreSQL connection string.

Alternatively, if you are instantiating `PostgreSQLBackend` manually in your code, you can pass the connection string directly to its constructor (though using the environment variable is often preferred for flexibility).

**4. Usage Example:**

To use the `PostgreSQLBackend`, you need to instantiate it and pass it to the `LLMAccounting` class:

```python
from llm_accounting import LLMAccounting
from llm_accounting.backends.postgresql import PostgreSQLBackend # Import the PostgreSQLBackend
# from datetime import datetime # if you are passing timestamps or querying by date

# Option 1: Connection string from environment variable POSTGRESQL_CONNECTION_STRING
# Ensure POSTGRESQL_CONNECTION_STRING is set in your environment before running the script.
# For example: export POSTGRESQL_CONNECTION_STRING="your_postgresql_uri_here"

postgresql_backend_env = PostgreSQLBackend() # Reads from environment variable
accounting_postgresql_env = LLMAccounting(backend=postgresql_backend_env)

# The backend will automatically manage its connection.

# Example: Track usage
accounting_postgresql_env.track_usage(
    model="gpt-3.5-turbo",
    prompt_tokens=50,
    completion_tokens=100,
    cost=0.00015
)
print("Usage tracked with PostgreSQL backend (from env var).")

# Example: Get stats for a period
end_date = datetime.now()
start_date = end_date - timedelta(days=7) # Last 7 days
stats = accounting_postgresql_env.get_period_stats(start_date, end_date)
print(f"PostgreSQL backend stats: {stats.sum_cost}")

# Option 2: Pass connection string directly
# Replace with your actual connection string if testing this way.
postgresql_connection_str = "postgresql://user:pass@localhost:5432/mydatabase"
postgresql_backend_direct = PostgreSQLBackend(postgresql_connection_string=postgresql_connection_str)
accounting_postgresql_direct = LLMAccounting(backend=postgresql_backend_direct)

accounting_postgresql_direct.track_usage(
    model="gpt-4",
    prompt_tokens=200,
    completion_tokens=400,
    cost=0.006
)
print("Usage tracked with PostgreSQL backend (direct connection string).")

# It's good practice to explicitly close the accounting instances when done.
accounting_postgresql_env.close()
accounting_postgresql_direct.close()
```

**Error Handling/Notes:**

*   The `PostgreSQLBackend` includes error handling for common database connection and operation issues, raising `ConnectionError` or `psycopg2.Error` as appropriate.
*   Ensure your PostgreSQL database instance is active and accessible from the environment where your application is running.
*   Refer to your PostgreSQL documentation (or cloud provider's documentation like Neon) for details on managing your database, connection pooling, and security best practices.

### Custom Backend Implementation

The `llm-accounting` library is designed with a pluggable backend system, allowing you to integrate with any database or data storage solution by implementing the `BaseBackend` abstract class. This is particularly useful for integrating with existing infrastructure or custom data handling requirements.

Here's how you can implement your own custom backend, using the `MockBackend` as a simplified example:

1.  **Define your Backend Class**: Create a new class that inherits from `llm_accounting.backends.base.BaseBackend`. You will need to implement all abstract methods defined in `BaseBackend`.

    ```python
    # my_custom_backend.py
    from datetime import datetime
    from typing import Dict, List, Tuple, Any, Optional

    from llm_accounting.backends.base import BaseBackend, UsageEntry, UsageStats

    class MyCustomBackend(BaseBackend):
        def __init__(self):
            self.usage_storage = [] # Example: a list to store UsageEntry objects
            # Add storage for limits if needed

        def initialize(self) -> None:
            print("MyCustomBackend: Initializing connection/resources...")
            # Implement your database connection or resource setup here

        def _ensure_connected(self) -> None:
            print("MyCustomBackend: Ensuring connection is active...")
            # Implement logic to ensure connection is active, e.g., self.initialize() if not connected

        def insert_usage(self, entry: UsageEntry) -> None:
            self._ensure_connected()
            print(f"MyCustomBackend: Inserting usage for model {entry.model}")
            self.usage_storage.append(entry)
            # Implement logic to save 'entry' to your database

        # ... (implement other abstract methods like get_period_stats, get_model_stats, etc.) ...
        # ... (get_model_rankings, purge, tail, close, execute_query) ...
        # ... (get_usage_limits, insert_usage_limit, get_accounting_entries_for_quota) ...
        # ... (delete_usage_limit) ...

        def get_period_stats(self, start: datetime, end: datetime) -> UsageStats:
            self._ensure_connected()
            # Dummy implementation
            return UsageStats()

        def get_model_stats(self, start: datetime, end: datetime) -> List[Tuple[str, UsageStats]]:
            self._ensure_connected()
            # Dummy implementation
            return []
        
        def get_model_rankings(self, start: datetime, end: datetime) -> Dict[str, List[Tuple[str, Any]]]:
            self._ensure_connected()
            # Dummy implementation
            return {}

        def purge(self) -> None:
            self._ensure_connected()
            self.usage_storage = []
        
        def tail(self, n: int = 10) -> List[UsageEntry]:
            self._ensure_connected()
            return self.usage_storage[-n:]

        def close(self) -> None:
            print("MyCustomBackend: Closing connection/resources...")

        def execute_query(self, query: str) -> List[Dict[str, Any]]:
            self._ensure_connected()
            print(f"MyCustomBackend: Executing custom query: {query}")
            return []
            
        def get_usage_limits(self, scope: Optional[LimitScope] = None, model: Optional[str] = None, username: Optional[str] = None, caller_name: Optional[str] = None) -> List[UsageLimit]:
            self._ensure_connected()
            # Dummy implementation
            return []

        def get_accounting_entries_for_quota(self, start_time: datetime, limit_type: LimitType, model: Optional[str] = None, username: Optional[str] = None, caller_name: Optional[str] = None) -> float:
            self._ensure_connected()
            # Dummy implementation
            return 0.0

        def insert_usage_limit(self, limit: UsageLimit) -> None:
            self._ensure_connected()
            # Dummy implementation
            pass

        def delete_usage_limit(self, limit_id: int) -> None:
            self._ensure_connected()
            # Dummy implementation
            pass
    ```

2.  **Integrate with `LLMAccounting`**: Once your custom backend is implemented, you can pass an instance of it to the `LLMAccounting` constructor:

```python
from llm_accounting import LLMAccounting
from my_custom_backend import MyCustomBackend # Import your custom backend

# Instantiate your custom backend
custom_backend = MyCustomBackend()

# Pass it to LLMAccounting
accounting_custom = LLMAccounting(backend=custom_backend)

# Now, all accounting operations will use your custom backend
accounting_custom.track_usage(model="custom_model", prompt_tokens=10, cost=0.001)
stats = accounting_custom.get_period_stats(datetime.now(), datetime.now())
print(f"Custom backend stats: {stats.sum_cost}")
accounting_custom.close()
```

By following this pattern, you can extend `llm-accounting` to work seamlessly with virtually any data storage solution, providing maximum flexibility for your application's needs.

## Projects Utilizing LLM Accounting

- **LLM Wrapper MCP Server** (`llm-wrapper-mcp-server`)
  - GitHub: [https://github.com/matdev83/llm-wrapper-mcp-server](https://github.com/matdev83/llm-wrapper-mcp-server)
  - Description: A Model Context Protocol (MCP) server wrapper designed to facilitate seamless interaction with various Large Language Models (LLMs) through a standardized interface. This project enables developers to integrate LLM capabilities into their applications by providing a robust and flexible server that handles LLM calls, tool execution, and result processing.

We will be adding examples of projects that utilize `llm-accounting` in the nearest future to demonstrate reference usage.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.


## License

This project is licensed under the MIT License - see the LICENSE file for details.
