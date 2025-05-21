# LLM Accounting

A Python package for tracking and analyzing LLM usage across different models and applications.

## Features

- Track usage of different LLM models
- Record token counts (prompt, completion, total)
- Track costs and execution times
- Support for local token counting
- Pluggable backend system (SQLite included)
- CLI interface for viewing and tracking usage statistics
- Support for tracking caller application and username
- Automatic database schema migration
- Strict model name validation
- Automatic timestamp handling

## Installation

```bash
pip install llm-accounting
```

For specific database backends, install the corresponding optional dependencies:

```bash
# For SQLite (default)
pip install llm-accounting[sqlite]

# For MySQL
pip install llm-accounting[mysql]

# For PostgreSQL
pip install llm-accounting[postgresql]
```

## Usage

### Basic Usage

```python
from llm_accounting import LLMAccounting

async with LLMAccounting() as accounting:
    # Track usage (model name is required, timestamp is optional)
    await accounting.track_usage(
        model="gpt-4",  # Required: name of the LLM model
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        cost=0.002,
        execution_time=1.5,
        caller_name="my_app",  # Optional: name of the calling application
        username="john_doe",   # Optional: name of the user
        timestamp=None         # Optional: if None, current time will be used
    )
    
    # Get statistics
    stats = await accounting.get_period_stats(start_date, end_date)
    model_stats = await accounting.get_model_stats(start_date, end_date)
    rankings = await accounting.get_model_rankings(start_date, end_date)
```

### CLI Usage

```bash
# Track a new usage entry (model name is required, timestamp is optional)
llm-accounting track \
    --model gpt-4 \  # Required: name of the LLM model
    --prompt-tokens 100 \
    --completion-tokens 50 \
    --total-tokens 150 \
    --cost 0.002 \
    --execution-time 1.5 \
    --caller-name my_app \
    --username john_doe \
    --timestamp "2024-01-01T12:00:00" \  # Optional: if not provided, current time will be used
    --cached-tokens 20 \  # Optional: number of tokens retrieved from cache
    --reasoning-tokens 10  # Optional: number of tokens used for model reasoning

# Track with local token counts
llm-accounting track \
    --model gpt-4 \  # Required: name of the LLM model
    --prompt-tokens 100 \
    --completion-tokens 50 \
    --total-tokens 150 \
    --local-prompt-tokens 95 \
    --local-completion-tokens 48 \
    --local-total-tokens 143 \
    --cost 0.002 \
    --execution-time 1.5 \
    --cached-tokens 20 \
    --reasoning-tokens 10

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

# Execute custom SQL queries
llm-accounting select --query "SELECT model, COUNT(*) as count FROM accounting_entries GROUP BY model"
llm-accounting select --query "SELECT * FROM accounting_entries WHERE model = 'gpt-4' ORDER BY datetime DESC LIMIT 10"
```

### Shell Script Integration

The CLI can be easily integrated into shell scripts. Here's an example:

```bash
#!/bin/bash

# Track usage after an LLM API call (model name is required, timestamp is optional)
llm-accounting track \
    --model "gpt-4" \  # Required: name of the LLM model
    --prompt-tokens "$PROMPT_TOKENS" \
    --completion-tokens "$COMPLETION_TOKENS" \
    --total-tokens "$TOTAL_TOKENS" \
    --cost "$COST" \
    --execution-time "$EXECUTION_TIME" \
    --caller-name "my_script" \
    --username "$USER"
    # Timestamp is optional - if not provided, current time will be used

# Check daily usage
llm-accounting stats --daily
```

## Usage Limits and Quotas

The limits system allows configuring various usage constraints through a YAML configuration file (`limits.yaml`):

```yaml
# Global daily token limit
global:
  daily_tokens: 100000

# Per-model limits
models:
  gpt-4:
    hourly_requests: 50
    daily_tokens: 50000
  claude-2:
    concurrent_requests: 5

# User-specific limits  
users:
  john_doe:
    daily_requests: 200
```

CLI commands for managing limits:
```bash
# Check current usage against limits
llm-accounting limits check

# View limit configurations
llm-accounting limits show

# Force reset limits (admin only)
llm-accounting limits reset --model gpt-4
llm-accounting limits reset --user john_doe

# Example combining multiple limits
llm-accounting limits set \
  --global daily_tokens=150000 \
  --model gpt-4 hourly_requests=75 \
  --user jane_doe daily_requests=300
```

## Database Schema

The SQLite database includes the following fields:
- `id`: Unique identifier (handled internally by the database)
- `datetime`: Timestamp of the usage (automatically set if not provided)
- `model`: Name of the LLM model (required)
- `prompt_tokens`: Number of prompt tokens
- `completion_tokens`: Number of completion tokens
- `total_tokens`: Total number of tokens
- `local_prompt_tokens`: Number of locally counted prompt tokens
- `local_completion_tokens`: Number of locally counted completion tokens
- `local_total_tokens`: Total number of locally counted tokens
- `cost`: Cost of the API call
- `execution_time`: Execution time in seconds
- `caller_name`: Name of the calling application (optional)
- `username`: Name of the user (optional)
- `cached_tokens`: Number of tokens retrieved from cache (default: 0)
- `reasoning_tokens`: Number of tokens used for model reasoning (default: 0)

Note: The `id` field is managed internally by the database and is not exposed through the API. This ensures data integrity and prevents external manipulation of record identifiers.

## Backend Configuration

### SQLite (Default)

```python
from llm_accounting import LLMAccounting
from llm_accounting.backends.sqlite import SQLiteBackend

backend = SQLiteBackend(db_path='path/to/database.sqlite')
accounting = LLMAccounting(backend=backend)
```

### MySQL

```python
from llm_accounting import LLMAccounting
from llm_accounting.backends.mysql import MySQLBackend

backend = MySQLBackend(
    host='localhost',
    port=3306,
    user='user',
    password='password',
    database='llm_accounting'
)
accounting = LLMAccounting(backend=backend)
```

### PostgreSQL

```python
from llm_accounting import LLMAccounting
from llm_accounting.backends.postgresql import PostgreSQLBackend

backend = PostgreSQLBackend(
    host='localhost',
    port=5432,
    user='user',
    password='password',
    database='llm_accounting'
)
accounting = LLMAccounting(backend=backend)
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
