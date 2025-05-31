# Project Structure: LLM Accounting

This document provides a detailed overview of the `llm-accounting` project's structure, outlining the purpose of each directory and key files. The aim is to facilitate quick orientation for new contributors and LLM agents, enabling efficient understanding and navigation of the codebase.

## 1. Project Overview

`llm-accounting` is a system designed to track and manage LLM (Large Language Model) usage, including token consumption, costs, and rate limits. It provides a flexible backend system (supporting SQLite and PostgreSQL), a command-line interface (CLI) for interaction, and a robust testing suite.

## 2. Top-Level Files and Directories

Here's a breakdown of the main files and directories at the project root:

-   `.flake8`: Configuration file for `flake8`, a Python code linter, ensuring code quality and style consistency.
-   `.gitignore`: Specifies intentionally untracked files to be ignored by Git.
-   `CHANGELOG.md`: Logs important updates, releases, and the history of changes.
-   `LICENSE`: Contains the licensing information for the project.
-   `MANIFEST.in`: Specifies non-Python files to be included in the Python distribution package.
-   `pyproject.toml`: Modern Python project configuration file.
-   `pytest.ini`: Configuration for `pytest`, the testing framework.
-   `README.md`: The main project README.
-   `requirements.txt`: Lists the project's Python dependencies.
-   `setup.py`: Traditional Python setup script for packaging and distribution.
-   `tox.ini`: Configuration for `tox`, a tool for automating testing in multiple Python environments.
-   `alembic/`: Contains Alembic environment and migration scripts for database schema management.
-   `data/`: Directory for storing application data (e.g., SQLite databases).
-   `docs/`: Contains project documentation, including this `STRUCTURE.md` file.
-   `llm_accounting/`: Top-level package for the LLM accounting system (editable install).
-   `src/`: Contains the main source code of the `llm-accounting` library.
-   `tests/`: Contains all unit and integration tests for the project.

## 3. `src/` Directory

The `src/` directory holds the core logic of the `llm-accounting` library.

### `src/llm_accounting/`

This is the main package for the LLM accounting system.

-   `__init__.py`: Initializes the `llm_accounting` package.
-   `audit_log.py`: Manages the auditing of LLM usage, recording events and interactions.
-   `db_migrations.py`: Contains functions related to database migrations.

#### `src/llm_accounting/backends/`

This sub-package defines the various database backends supported by the system.

-   `__init__.py`: Initializes the `backends` package.
-   `base.py`: Defines the abstract base classes and interfaces for all backend implementations.
-   `mock_backend.py`: A mock implementation of the backend for testing and development.
-   `postgresql.py`: Implements the PostgreSQL backend.
-   `sqlite_queries.py`: Contains SQL query definitions specific to the SQLite backend.
-   `sqlite_utils.py`: Utility functions for the SQLite backend, such as path validation.
-   `sqlite.py`: Implements the SQLite backend.
-   `csv_backend.py`: Implements the CSV backend, storing accounting data in CSV files.

##### `src/llm_accounting/backends/mock_backend_parts/`

Components specific to the mock backend.

-   `connection_manager.py`: Manages mock database connections.
-   `limit_manager.py`: Handles mock limit enforcement.
-   `query_executor.py`: Executes mock queries.
-   `stats_manager.py`: Manages mock usage statistics.
-   `usage_manager.py`: Manages mock usage data.

##### `src/llm_accounting/backends/postgresql_backend_parts/`

Components specific to the PostgreSQL backend.

-   `connection_manager.py`: Manages PostgreSQL database connections.
-   `data_deleter.py`: Handles deletion of data in PostgreSQL.
-   `data_inserter.py`: Handles insertion of data into PostgreSQL.
-   `limit_manager.py`: Manages limit enforcement for PostgreSQL.
-   `query_executor.py`: Executes queries against PostgreSQL.
-   `query_reader.py`: Reads data from PostgreSQL.
-   `quota_reader.py`: Reads quota-related data from PostgreSQL.
-   `schema_manager.py`: Manages the database schema for PostgreSQL.

#### `src/llm_accounting/cli/`

This sub-package contains the command-line interface (CLI) implementation.

-   `main.py`: The entry point for the CLI application.
-   `parsers.py`: Defines argument parsers for CLI commands.
-   `utils.py`: Utility functions used by the CLI.

##### `src/llm_accounting/cli/commands/`

Individual CLI commands.

-   `limits.py`: CLI command for managing and viewing usage limits.
-   `log_event.py`: CLI command for logging arbitrary events.
-   `purge.py`: CLI command for purging old usage data.
-   `select.py`: CLI command for querying and selecting usage data.
-   `stats.py`: CLI command for displaying usage statistics.
-   `tail.py`: CLI command for tailing (monitoring) real-time usage.
-   `track.py`: CLI command for tracking LLM usage.

#### `src/llm_accounting/models/`

Defines data models used throughout the application.

-   `__init__.py`: Initializes the `models` package.
-   `accounting.py`: Defines the SQLAlchemy ORM model for `AccountingEntry`.
-   `audit.py`: Defines the SQLAlchemy ORM model for `AuditLogEntryModel`.
-   `base.py`: Base models or common model utilities.
-   `limits.py`: Data models for defining and managing usage limits.

#### `src/llm_accounting/services/`

Contains business logic and services.

-   `quota_service.py`: Provides services related to quota management and enforcement.

## 4. `tests/` Directory

This directory contains all tests for the `llm-accounting` project, organized to mirror the `src/` directory structure.

-   `__init__.py`: Initializes the `tests` package.
-   `conftest.py`: Contains fixtures and hooks for `pytest` that are shared across multiple test files.
-   `test_audit_log.py`: Tests for the `audit_log` module.
-   `test_migrations.py`: Tests for the Alembic database migration system.

### `tests/accounting/`

Tests related to the core accounting logic.

-   `test_global_limits.py`: Tests for global usage limits.
-   `test_model_limits.py`: Tests for limits specific to LLM models.
-   `test_multiple_limit_types.py`: Tests scenarios involving multiple types of limits.
-   `test_user_caller_limits.py`: Tests for limits based on user or caller identity.

### `tests/api_compatibility/`

Tests to ensure API compatibility.

-   `test_audit_logger_api.py`: Tests the API of the audit logger.
-   `test_cli_api.py`: Tests the public API of the CLI.
-   `test_llm_accounting_api.py`: Tests the main `llm-accounting` library API.

### `tests/backends/`

Tests for the various backend implementations.

-   `mock_backends.py`: Tests specific to the mock backend.
-   `test_base.py`: Tests for the base backend interfaces.
-   `test_postgresql.py`: Tests for the PostgreSQL backend.
-   `test_sqlite.py`: Tests for the SQLite backend.
-   `test_csv_backend.py`: Contains unit tests for the `CSVBackend`.
-   `test_usage_models.py`: Tests for usage-related data models.

#### `tests/backends/postgresql_backend_tests/`

Detailed tests for the PostgreSQL backend.

-   `__init__.py`: Initializes the package.
-   `base_test_postgresql.py`: Base test classes for PostgreSQL tests.
-   `test_postgresql_audit_log.py`: Tests audit logging in PostgreSQL.
-   `test_postgresql_init_and_connection.py`: Tests initialization and connection to PostgreSQL.
-   `test_postgresql_query_delegation.py`: Tests query delegation in PostgreSQL.
-   `test_postgresql_query_execution.py`: Tests query execution in PostgreSQL.
-   `test_postgresql_quota_accounting.py`: Tests quota accounting in PostgreSQL.
-   `test_postgresql_usage_insertion.py`: Tests usage data insertion in PostgreSQL.
-   `test_postgresql_usage_limits.py`: Tests usage limits enforcement in PostgreSQL.

#### `tests/backends/sqlite_backend_tests/`

Detailed tests for the SQLite backend.

-   `conftest.py`: Fixtures specific to SQLite backend tests.
-   `test_sqlite_audit_log.py`: Tests audit logging in SQLite.
-   `test_sqlite_init_and_usage.py`: Tests initialization and basic usage of SQLite backend.
-   `test_sqlite_stats_and_purge.py`: Tests statistics and purging functionality in SQLite.
-   `test_sqlite_usage_limits.py`: Tests usage limits enforcement in SQLite.

### `tests/cli/`

Tests for the command-line interface.

-   `test_cli_limits_project.py`: Tests the `limits` CLI command.
-   `test_cli_log_event.py`: Tests the `log_event` CLI command.
-   `test_cli_purge.py`: Tests the `purge` CLI command.
-   `test_cli_stats.py`: Tests the `stats` CLI command.
-   `test_cli_tail.py`: Tests the `tail` CLI command.
-   `test_cli_track.py`: Tests the `track` CLI command.
-   `test_cli_version.py`: Tests the CLI version command.
-   `test_select_project.py`: Tests the `select` CLI command.

#### `tests/cli/test_select/`

Tests for the `select` CLI command's specific functionalities.

-   `__init__.py`: Initializes the package.
-   `conftest.py`: Fixtures specific to `select` command tests.

##### `tests/cli/test_select/select/`

Further granular tests for the `select` command.

-   `__init__.py`: Initializes the package.
-   `conftest.py`: Fixtures specific to these granular `select` tests.
-   `test_aggregation.py`: Tests aggregation queries with `select`.
-   `test_basic_query.py`: Tests basic `select` queries.
-   `test_no_results.py`: Tests `select` command behavior when no results are found.
-   `test_non_select_query.py`: Tests `select` command behavior with non-select queries (should fail or be handled).
-   `test_output_formatting.py`: Tests the formatting of `select` command output.
-   `test_syntax_error.py`: Tests `select` command error handling for syntax errors.

### `tests/core/`

Tests for core accounting functionalities.

-   `__init__.py`: Initializes the package.
-   `test_accounting_purge.py`: Tests the core purge logic.
-   `test_accounting_stats.py`: Tests the core statistics generation logic.
-   `test_accounting_tracking.py`: Tests the core usage tracking logic.
-   `test_accounting_validation.py`: Tests validation rules for accounting data.
-   `test_project_quota_service.py`: Tests the project-level quota service.
-   `test_quota_service.py`: Tests the general quota service.

## 5. `docs/` Directory

This directory is dedicated to project documentation.

-   `STRUCTURE.md`: This file, detailing the project's directory and file structure.

## 6. `data/` Directory

This directory is intended for storing application data. In a typical setup, this might include:

-   SQLite database files (e.g., `llm_accounting.db`).
-   Configuration files that are not part of the source code.

## 7. `logs/` Directory

This directory is used for storing application logs generated during runtime. These logs are crucial for debugging, monitoring, and understanding the application's behavior.
