import os
from datetime import datetime, timedelta
from llm_accounting import LLMAccounting
from llm_accounting.backends.sqlite import SQLiteBackend
from llm_accounting.models.limits import LimitScope, LimitType, TimeInterval
from llm_accounting.audit_log import AuditLogger
import time

# Define custom database filenames
custom_accounting_db_filename = "my_custom_accounting.sqlite"
custom_audit_db_filename = "my_custom_audit.sqlite"

# Ensure the directory for the custom DB exists (if not in current dir)
# For simplicity, we'll assume it's in the current directory or 'data/'
# If you want it in a specific folder, e.g., 'data/custom_dbs/', you'd do:
# os.makedirs(os.path.join('data', 'custom_dbs'), exist_ok=True)
# custom_db_filename = os.path.join('data', 'custom_dbs', 'my_custom_accounting.sqlite')

print(f"Initializing LLMAccounting with custom DB: {custom_accounting_db_filename}")

# 1. Initialize SQLiteBackend with the custom filename
sqlite_backend = SQLiteBackend(db_path=custom_accounting_db_filename)

# 2. Pass the custom backend to LLMAccounting
# Using a context manager ensures the connection is properly opened and closed
with LLMAccounting(backend=sqlite_backend) as accounting:
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

# Clean up the created database files
print("\nCleaning up created database files...")
if os.path.exists(custom_accounting_db_filename):
    os.remove(custom_accounting_db_filename)
    print(f"Removed {custom_accounting_db_filename}")
if os.path.exists(custom_audit_db_filename):
    os.remove(custom_audit_db_filename)
    print(f"Removed {custom_audit_db_filename}")

print("\nExample complete.")
