# LLM Accounting

A Python package for tracking and analyzing LLM usage across different models and applications. It is primarily designed as a library for integration into development process of LLM-based agentic workflow tooling, providing robust tracking capabilities. While its main use is as a library, it also provides a powerful CLI for scripting and batch workloads.

**Keywords**: LLM, accounting, usage tracking, cost management, token counting, agentic workflows, AI, Python

## Features

- Track usage of different LLM models
- Record token counts (prompt, completion, total)
- Track costs and execution times
- Support for local token counting
- Pluggable backend system (SQLite included, Neon/PostgreSQL fully supported)
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

# For Neon/PostgreSQL
pip install llm-accounting[neon]
```

## Usage

### Basic Usage

```python
from llm_accounting import LLMAccounting
# from llm_accounting.backends.sqlite import SQLiteBackend # Default
# from llm_accounting.backends.neon import NeonBackend # If using Neon
# from datetime import datetime # If providing timestamps or querying by date

# Default backend (SQLite)
# async with LLMAccounting() as accounting:
#     # Track usage (model name is required, timestamp is optional)
#     await accounting.track_usage(
#         model="gpt-4",  # Required: name of the LLM model
#         prompt_tokens=100,
#         completion_tokens=50,
#         total_tokens=150,
#         cost=0.002,
#         execution_time=1.5,
#         caller_name="my_app",  # Optional: name of the calling application
#         username="john_doe",   # Optional: name of the user
#         timestamp=None         # Optional: if None, current time will be used
#     )
#     
#     # Get statistics
#     # start_date = datetime(2024, 1, 1)
#     # end_date = datetime(2024, 1, 31)
#     # stats = await accounting.get_period_stats(start_date, end_date)
#     # model_stats = await accounting.get_model_stats(start_date, end_date)
#     # rankings = await accounting.get_model_rankings(start_date, end_date)
```
*Note: The `LLMAccounting` class's methods like `track_usage` are shown with `await` in previous examples. If these methods are indeed asynchronous, ensure your application is run in an async context (e.g., using `asyncio.run()`). The specific backend's methods (like `NeonBackend.initialize()`) might be synchronous; `LLMAccounting` should manage this interaction.*

### CLI Usage

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
    --timestamp "2024-01-01T12:00:00" \
    --cached-tokens 20 \
    --reasoning-tokens 10

# ... (other CLI examples remain the same) ...

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
# llm-accounting select --query "SELECT model, COUNT(*) as count FROM accounting_entries GROUP BY model"

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

You can specify the database backend directly via the CLI using the `--db-backend` option. This allows you to switch between `sqlite` (default) and `neon` without modifying code.

```bash
# Use SQLite backend (default behavior, --db-backend can be omitted)
llm-accounting --db-backend sqlite --db-file my_sqlite_db.sqlite stats --daily

# Use Neon backend
# Requires NEON_CONNECTION_STRING environment variable to be set, or provide it directly
llm-accounting --db-backend neon --neon-connection-string "postgresql://user:pass@host.neon.tech/dbname?sslmode=require" stats --daily

# Example: Track usage with Neon backend
llm-accounting --db-backend neon \
    --neon-connection-string "postgresql://user:pass@host.neon.tech/dbname?sslmode=require" \
    track \
    --model gpt-4 \
    --prompt-tokens 10 \
    --cost 0.0001
```
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

The database schema generally includes the following tables and key fields (specifics might vary slightly by backend, but `NeonBackend` adheres to this structure):

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
- `cached_tokens`: INTEGER - Number of tokens retrieved from cache.
- `reasoning_tokens`: INTEGER - Number of tokens used for model reasoning/tool use.

**`api_requests` Table (for quota tracking):**
- `id`: SERIAL PRIMARY KEY
- `model_name`: VARCHAR(255) NOT NULL
- `username`: VARCHAR(255)
- `caller_name`: VARCHAR(255)
- `input_tokens`: INTEGER
- `output_tokens`: INTEGER
- `cost`: DOUBLE PRECISION
- `timestamp`: TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP

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

*Note: The `id` fields are managed internally by the database.*

## Backend Configuration

### SQLite (Default)

The default backend is SQLite, which stores data in a local file.

```python
from llm_accounting import LLMAccounting
from llm_accounting.backends.sqlite import SQLiteBackend

# If you want to specify a custom path for the SQLite database:
# backend = SQLiteBackend(db_path='path/to/your_database.sqlite')
# accounting = LLMAccounting(backend=backend)

# Otherwise, LLMAccounting() uses a default SQLiteBackend:
accounting_sqlite = LLMAccounting()
# async with accounting_sqlite:
#     await accounting_sqlite.track_usage(model="gpt-3.5-turbo", cost=0.001)
```

### Neon Backend (PostgreSQL)

The `NeonBackend` provides a reference implementation for using a cloud-based PostgreSQL database with `llm-accounting`. It is specifically designed to work well with [Neon](https://neon.tech/) serverless Postgres, but it can also be used with any other standard PostgreSQL instance.

**1. Set Up Your Neon Database (User's Responsibility):**

To use `NeonBackend` with Neon, you'll need to set up your own database instance:

*   **Sign Up**: Go to [https://neon.tech/](https://neon.tech/) and sign up for an account. The free tier is suitable for experimentation and development.
*   **Create a Project**: In the Neon console, create a new project. This will be your serverless Postgres instance.
*   **Obtain Connection String**: Once the project is created, find your database's connection string (URI format). It will look something like this:
    ```
    postgresql://<user>:<password>@<host>.neon.tech:<port>/<dbname>?sslmode=require
    ```
    *Note: Neon typically requires `sslmode=require`.*

**2. Install Dependencies:**

The `NeonBackend` requires the `psycopg2-binary` package to communicate with PostgreSQL databases. You can install it as an extra dependency:

```bash
pip install llm-accounting[neon]
```

**3. Configuration:**

The `NeonBackend` primarily expects the database connection string to be available via the `NEON_CONNECTION_STRING` environment variable.

```bash
export NEON_CONNECTION_STRING="postgresql://your_user:your_password@your_host.neon.tech:5432/your_dbname?sslmode=require"
```

Replace the placeholder values with your actual Neon connection string.

Alternatively, if you are instantiating `NeonBackend` manually in your code, you can pass the connection string directly to its constructor (though using the environment variable is often preferred for flexibility).

**4. Usage Example:**

To use the `NeonBackend`, you need to instantiate it and pass it to the `LLMAccounting` class:

```python
from llm_accounting import LLMAccounting
from llm_accounting.backends.neon import NeonBackend # Import the NeonBackend
# from datetime import datetime # if you are passing timestamps or querying by date

# Option 1: Connection string from environment variable NEON_CONNECTION_STRING
# Ensure NEON_CONNECTION_STRING is set in your environment before running the script.
# For example: export NEON_CONNECTION_STRING="your_neon_uri_here"

neon_backend_env = NeonBackend() # Reads from environment variable
accounting_neon_env = LLMAccounting(backend=neon_backend_env)

# The LLMAccounting class's methods might be async or sync.
# The NeonBackend's initialize/close methods are synchronous.
# This example assumes LLMAccounting manages the async/sync interaction if its methods are async.
# For simplicity, direct calls are shown here. If LLMAccounting methods are async, use `async with`.

# with accounting_neon_env: # Use `async with` if LLMAccounting methods are async
#     # Example: Track usage
#     accounting_neon_env.track_usage( # Use `await` if track_usage is async
#         model="gpt-3.5-turbo",
#         prompt_tokens=50,
#         completion_tokens=100,
#         cost=0.00015
#     )
#     print("Usage tracked with Neon backend (from env var).")
#     
#     # Example: Get stats for a period
#     # start_date = datetime(2024, 1, 1)
#     # end_date = datetime(2024, 1, 31)
#     # stats = accounting_neon_env.get_period_stats(start_date, end_date) # Use `await` if async
#     # print(stats)


# Option 2: Pass connection string directly
# Replace with your actual connection string if testing this way.
# neon_connection_str = "postgresql://user:pass@host.neon.tech/dbname?sslmode=require" 
# neon_backend_direct = NeonBackend(neon_connection_string=neon_connection_str)
# accounting_neon_direct = LLMAccounting(backend=neon_backend_direct)

# with accounting_neon_direct: # Use `async with` if LLMAccounting methods are async
#     accounting_neon_direct.track_usage( # Use `await` if track_usage is async
#         model="gpt-4",
#         prompt_tokens=200,
#         completion_tokens=400,
#         cost=0.006
#     )
#     print("Usage tracked with Neon backend (direct connection string).")
```

*Note on Asynchronous Operations: The main `LLMAccounting` class examples in this README use `async with` and `await`, suggesting asynchronous operation. The `NeonBackend` itself uses the synchronous `psycopg2` library. If `LLMAccounting`'s core methods are asynchronous, it should ideally handle the execution of synchronous backend operations in a way that doesn't block the async event loop (e.g., by using `asyncio.to_thread` or similar patterns). Users building fully asynchronous applications should be mindful of this potential interaction.*

**Error Handling/Notes:**

*   The `NeonBackend` includes error handling for common database connection and operation issues, raising `ConnectionError` or `psycopg2.Error` as appropriate.
*   Ensure your Neon database instance is active and accessible from the environment where your application is running.
*   Refer to the Neon documentation for details on managing your database, connection pooling, and security best practices.

### Custom Backend Implementation

The `llm-accounting` library is designed with a pluggable backend system, allowing you to integrate with any database or data storage solution by implementing the `BaseBackend` abstract class. This is particularly useful for integrating with existing infrastructure or custom data handling requirements.

Here's how you can implement your own custom backend, using the `MockBackend` as a simplified example:

1.  **Define your Backend Class**: Create a new class that inherits from `llm_accounting.backends.base.BaseBackend`. You will need to implement all abstract methods defined in `BaseBackend`.

    ```python
    # my_custom_backend.py
    from datetime import datetime
    from typing import Dict, List, Tuple, Any, Optional

    from llm_accounting.backends.base import BaseBackend, UsageEntry, UsageStats, APIRequest # Added APIRequest

    class MyCustomBackend(BaseBackend):
        def __init__(self):
            self.usage_storage = [] # Example: a list to store UsageEntry objects
            self.request_storage = [] # Example: a list to store APIRequest objects
            # Add storage for limits if needed

        def initialize(self) -> None:
            print("MyCustomBackend: Initializing connection/resources...")
            # Implement your database connection or resource setup here

        def insert_usage(self, entry: UsageEntry) -> None:
            print(f"MyCustomBackend: Inserting usage for model {entry.model}")
            self.usage_storage.append(entry)
            # Implement logic to save 'entry' to your database

        def insert_api_request(self, request: APIRequest) -> None: # New method from BaseBackend
            print(f"MyCustomBackend: Inserting API request for model {request.model_name}")
            self.request_storage.append(request)
            # Implement logic to save 'request' to your database

        # ... (implement other abstract methods like get_period_stats, get_model_stats, etc.) ...
        # ... (get_model_rankings, purge, tail, close, execute_query) ...
        # ... (get_usage_limits, insert_usage_limit, get_api_requests_for_quota) ...
        # ... (get_usage_costs, set_usage_limit, get_usage_limit, record_api_request (from dict)) ...

        def get_period_stats(self, start: datetime, end: datetime) -> UsageStats:
            # Dummy implementation
            return UsageStats()

        def get_model_stats(self, start: datetime, end: datetime) -> List[Tuple[str, UsageStats]]:
            # Dummy implementation
            return []
        
        def get_model_rankings(self, start: datetime, end: datetime) -> Dict[str, List[Tuple[str, Any]]]:
            # Dummy implementation
            return {}

        def purge(self) -> None:
            self.usage_storage = []
            self.request_storage = []
        
        def tail(self, n: int = 10) -> List[UsageEntry]:
            return self.usage_storage[-n:]

        def close(self) -> None:
            print("MyCustomBackend: Closing connection/resources...")

        def execute_query(self, query: str) -> List[Dict[str, Any]]: # Corrected return type
            print(f"MyCustomBackend: Executing custom query: {query}")
            return []
            
        # You would also need to implement other methods from BaseBackend like:
        # get_usage_limits, insert_usage_limit, get_api_requests_for_quota,
        # get_usage_costs, set_usage_limit, get_usage_limit, record_api_request (dict version)
    ```

2.  **Integrate with `LLMAccounting`**: Once your custom backend is implemented, you can pass an instance of it to the `LLMAccounting` constructor:

    ```python
    from llm_accounting import LLMAccounting
    # from my_custom_backend import MyCustomBackend # Import your custom backend

    # Instantiate your custom backend
    # custom_backend = MyCustomBackend()

    # Pass it to LLMAccounting
    # accounting_custom = LLMAccounting(backend=custom_backend)

    # Now, all accounting operations will use your custom backend
    # with accounting_custom: # Use `async with` if LLMAccounting methods are async
    #     accounting_custom.track_usage(model="custom_model", prompt_tokens=10, cost=0.001) # Use `await` if async
    #     # stats = accounting_custom.get_period_stats(datetime.now(), datetime.now()) # Use `await` if async
    #     # ... and so on
    ```

By following this pattern, you can extend `llm-accounting` to work seamlessly with virtually any data storage solution, providing maximum flexibility for your application's needs.

## Projects Utilizing LLM Accounting

We will be adding examples of projects that utilize `llm-accounting` in the nearest future to demonstrate reference usage.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
