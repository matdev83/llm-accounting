# Project Structure and Agent Guidelines: LLM Accounting

This document serves as a comprehensive guide for software development agents working on the `llm-accounting` project. It outlines the project's structure, key files, and essential software development principles that all agents **MUST** adhere to. The goal is to ensure consistency, maintainability, and high-quality code throughout the development lifecycle.

## 1. Project Overview

`llm-accounting` is a system designed to track and manage LLM (Large Language Model) usage, including token consumption, costs, and rate limits. It provides a flexible backend system (supporting SQLite and PostgreSQL), a command-line interface (CLI) for interaction, and a robust testing suite.

## 2. Top-Level Files and Directories

Here's a breakdown of the main files and directories at the project root:

- `.flake8`: Configuration file for `flake8`, a Python code linter, ensuring code quality and style consistency.
- `.gitignore`: Specifies intentionally untracked files to be ignored by Git.
- `AGENTS.MD`: This file, detailing project structure and agent guidelines.
- `LICENSE`: Contains the licensing information for the project.
- `MANIFEST.in`: Specifies non-Python files to be included in the Python distribution package.
- `pyproject.toml`: Modern Python project configuration file. All dependencies
  are managed here; there is no separate `requirements.txt` file.
- `pytest.ini`: Configuration for `pytest`, the testing framework.
- `README.md`: The main project README.
- `setup.py`: Traditional Python setup script for packaging and distribution.
- `tox.ini`: Configuration for `tox`, a tool for automating testing in multiple Python environments.
- `alembic.ini`: Configuration file for Alembic, the database migration tool.
- `alembic/`: Contains Alembic environment and migration scripts for database schema management.
- `data/`: Directory for storing application data (e.g., SQLite databases).
- `docs/`: Contains project documentation (excluding `AGENTS.MD`).
- `llm_accounting/`: Top-level package for the LLM accounting system (editable install).
- `release_orchestrator.py`: Script for orchestrating releases.
- `src/`: Contains the main source code of the `llm-accounting` library.
- `tests/`: Contains all unit and integration tests for the project.
- `version_manager.py`: Script for managing project versions.

## 3. `src/` Directory

The `src/` directory holds the core logic of the `llm-accounting` library.

### `src/llm_accounting/`

This is the main package for the LLM accounting system.

- `__init__.py`: Initializes the `llm_accounting` package.
- `audit_log.py`: Manages the auditing of LLM usage, recording events and interactions.
- `db_migrations.py`: Contains functions related to database migrations.

#### `src/llm_accounting/backends/`

This sub-package defines the various database backends supported by the system.

- `__init__.py`: Initializes the `backends` package.
- `base.py`: Defines the abstract base classes and interfaces for all backend implementations.
- `mock_backend.py`: A mock implementation of the backend for testing and development.
- `postgresql.py`: Implements the PostgreSQL backend.
- `sqlite_queries.py`: Contains SQL query definitions specific to the SQLite backend.
- `sqlite_utils.py`: Utility functions for the SQLite backend, such as path validation.
- `sqlite.py`: Implements the SQLite backend.

##### `src/llm_accounting/backends/mock_backend_parts/`

Components specific to the mock backend.

- `connection_manager.py`: Manages mock database connections.
- `limit_manager.py`: Handles mock limit enforcement.
- `query_executor.py`: Executes mock queries.
- `stats_manager.py`: Manages mock usage statistics.
- `usage_manager.py`: Manages mock usage data.

##### `src/llm_accounting/backends/sqlite_backend_parts/`

Components specific to the SQLite backend.

- `audit_log_manager.py`: Manages audit log operations for SQLite.
- `connection_manager.py`: Manages SQLite database connections.
- `limit_manager.py`: Handles SQLite limit enforcement.
- `query_executor.py`: Executes SQLite queries.
- `usage_manager.py`: Manages SQLite usage data.

##### `src/llm_accounting/backends/postgresql_backend_parts/`

Components specific to the PostgreSQL backend.

- `connection_manager.py`: Manages PostgreSQL database connections.
- `data_deleter.py`: Handles deletion of data in PostgreSQL.
- `data_inserter.py`: Handles insertion of data into PostgreSQL.
- `limit_manager.py`: Manages limit enforcement for PostgreSQL.
- `query_executor.py`: Executes queries against PostgreSQL.
- `query_reader.py`: Reads data from PostgreSQL.
- `quota_reader.py`: Reads quota-related data from PostgreSQL.
- `schema_manager.py`: Manages the database schema for PostgreSQL.

#### `src/llm_accounting/cli/`

This sub-package contains the command-line interface (CLI) implementation. The CLI supports configuring
separate database backends for accounting data and audit logs via the `--audit-db-*` options.

- `main.py`: The entry point for the CLI application.
- `parsers.py`: Defines argument parsers for CLI commands.
- `utils.py`: Utility functions used by the CLI.

##### `src/llm_accounting/cli/commands/`

Individual CLI commands.

- `limits.py`: CLI command for managing and viewing usage limits.
- `log_event.py`: CLI command for logging arbitrary events.
- `purge.py`: CLI command for purging old usage data.
- `select.py`: CLI command for querying and selecting usage data.
- `stats.py`: CLI command for displaying usage statistics.
- `tail.py`: CLI command for tailing (monitoring) real-time usage.
- `track.py`: CLI command for tracking LLM usage.

#### `src/llm_accounting/models/`

Defines data models used throughout the application.

- `__init__.py`: Initializes the `models` package.
- `accounting.py`: Defines the SQLAlchemy ORM model for `AccountingEntry`.
- `audit.py`: Defines the SQLAlchemy ORM model for `AuditLogEntryModel`.
- `base.py`: Base models or common model utilities.
- `limits.py`: Data models for defining and managing usage limits.

#### `src/llm_accounting/services/`

Contains business logic and services.

- `quota_service.py`: Provides services related to quota management and enforcement.

#### `src/llm_accounting/services/quota_service_parts/`

Components specific to the quota service.

- `_cache_manager.py`: Manages caching for quota service.
- `_limit_evaluator.py`: Evaluates limits for the quota service.

## 4. `tests/` Directory

This directory contains all tests for the `llm-accounting` project, organized to mirror the `src/` directory structure.

- `__init__.py`: Initializes the `tests` package.
- `conftest.py`: Contains fixtures and hooks for `pytest` that are shared across multiple test files.
- `test_audit_log.py`: Tests for the `audit_log` module.
- `test_migrations.py`: Tests for the Alembic database migration system.

### `tests/accounting/`

Tests related to the core accounting logic.

- `test_account_model_limits.py`: Tests for account-specific model limits.
- `test_comprehensive_limits.py`: Comprehensive tests for various limit scenarios.
- `test_global_limits.py`: Tests for global usage limits.
- `test_model_limits.py`: Tests for limits specific to LLM models.
- `test_multiple_limit_types.py`: Tests scenarios involving multiple types of limits.
- `test_rolling_limits.py`: Tests for rolling window limits.
- `test_user_caller_limits.py`: Tests for limits based on user or caller identity.

#### `tests/accounting/rolling_limits_tests/`

Detailed tests for rolling limits.

- `base_test_rolling_limits.py`: Base test classes for rolling limits.
- `test_day_rolling_limits.py`: Tests for daily rolling limits.
- `test_hour_rolling_limits.py`: Tests for hourly rolling limits.
- `test_minute_rolling_limits.py`: Tests for minute rolling limits.
- `test_mixed_rolling_limits.py`: Tests for mixed rolling limit types.
- `test_month_rolling_limits.py`: Tests for monthly rolling limits.
- `test_second_rolling_limits.py`: Tests for second rolling limits.
- `test_week_rolling_limits.py`: Tests for weekly rolling limits.

### `tests/api_compatibility/`

Tests to ensure API compatibility.

- `test_audit_logger_api.py`: Tests the API of the audit logger.
- `test_cli_api.py`: Tests the public API of the CLI.
- `test_llm_accounting_api.py`: Tests the main `llm-accounting` library API.

### `tests/backends/`

Tests for the various backend implementations.

- `mock_backends.py`: Tests specific to the mock backend.
- `test_base.py`: Tests for the base backend interfaces.
- `test_postgresql.py`: Tests for the PostgreSQL backend.
- `test_sqlite.py`: Tests for the SQLite backend.
- `test_usage_models.py`: Tests for usage-related data models.

#### `tests/backends/postgresql_backend_tests/`

Detailed tests for the PostgreSQL backend.

- `__init__.py`: Initializes the package.
- `base_test_postgresql.py`: Base test classes for PostgreSQL tests.
- `test_postgresql_audit_log.py`: Tests audit logging in PostgreSQL.
- `test_postgresql_init_and_connection.py`: Tests initialization and connection to PostgreSQL.
- `test_postgresql_migrations_cache.py`: Tests migration caching in PostgreSQL.
- `test_postgresql_query_delegation.py`: Tests query delegation in PostgreSQL.
- `test_postgresql_query_execution.py`: Tests query execution in PostgreSQL.
- `test_postgresql_quota_accounting.py`: Tests quota accounting in PostgreSQL.
- `test_postgresql_usage_insertion.py`: Tests usage data insertion in PostgreSQL.
- `test_postgresql_usage_limits.py`: Tests usage limits enforcement in PostgreSQL.

#### `tests/backends/sqlite_backend_tests/`

Detailed tests for the SQLite backend.

- `conftest.py`: Fixtures specific to SQLite backend tests.
- `test_sqlite_audit_log.py`: Tests audit logging in SQLite.
- `test_sqlite_init_and_usage.py`: Tests initialization and basic usage of SQLite backend.
- `test_sqlite_migrations_cache.py`: Tests migration caching in SQLite.
- `test_sqlite_stats_and_purge.py`: Tests statistics and purging functionality in SQLite.
- `test_sqlite_usage_limits.py`: Tests usage limits enforcement in SQLite.

### `tests/cli/`

Tests for the command-line interface.

- `test_cli_limits_project.py`: Tests the `limits` CLI command.
- `test_cli_log_event.py`: Tests the `log_event` CLI command.
- `test_cli_purge.py`: Tests the `purge` CLI command.
- `test_cli_stats.py`: Tests the `stats` CLI command.
- `test_cli_tail.py`: Tests the `tail` CLI command.
- `test_cli_track.py`: Tests the `track` CLI command.
- `test_cli_version.py`: Tests the CLI version command.
- `test_select_project.py`: Tests the `select` CLI command.

#### `tests/cli/test_select/`

Tests for the `select` CLI command's specific functionalities.

- `__init__.py`: Initializes the package.
- `conftest.py`: Fixtures specific to `select` command tests.

##### `tests/cli/test_select/select/`

Further granular tests for the `select` command.

- `__init__.py`: Initializes the package.
- `conftest.py`: Fixtures specific to these granular `select` tests.
- `test_aggregation.py`: Tests aggregation queries with `select`.
- `test_basic_query.py`: Tests basic `select` queries.
- `test_no_results.py`: Tests `select` command behavior when no results are found.
- `test_non_select_query.py`: Tests `select` command behavior with non-select queries (should fail or be handled).
- `test_output_formatting.py`: Tests the formatting of `select` command output.
- `test_syntax_error.py`: Tests `select` command error handling for syntax errors.

### `tests/core/`

Tests for core accounting functionalities.

- `__init__.py`: Initializes the package.
- `test_accounting_purge.py`: Tests the core purge logic.
- `test_accounting_stats.py`: Tests the core statistics generation logic.
- `test_accounting_tracking.py`: Tests the core usage tracking logic.
- `test_accounting_validation.py`: Tests validation rules for accounting data.
- `test_output_silence.py`: Tests for silencing output.
- `test_project_quota_service.py`: Tests the project-level quota service.
- `test_quota_service.py`: Tests the general quota service.

#### `tests/core/quota_service_tests/`

Tests specific to the quota service.

## 5. `docs/` Directory

This directory is dedicated to project documentation, excluding agent-specific guidelines.

- `PRERELEASE-REVIEW.md`: Documentation for pre-release review processes.

## 6. `data/` Directory

This directory is intended for storing application data. In a typical setup, this might include:

- SQLite database files (e.g., `llm_accounting.db`).
- Configuration files that are not part of the source code.

## 7. `logs/` Directory

This directory is used for storing application logs generated during runtime. These logs are crucial for debugging, monitoring, and understanding the application's behavior.

## 8. Software Development Principles for Agents

All software development agents contributing to this project **MUST** strictly adhere to the following principles to ensure code quality, maintainability, and scalability.

### 8.1. Layered, Modular Architecture

Agents should strive to maintain and enhance the existing layered and modular architecture. This means:

- **Separation of Concerns**: Each module or component should have a single, well-defined responsibility.
- **Loose Coupling**: Components should be as independent as possible, minimizing direct dependencies.
- **High Cohesion**: Elements within a module should be functionally related and work together towards a common goal.
- **Clear Interfaces**: Define explicit and stable interfaces between layers and modules to facilitate independent development and testing.

### 8.2. Following Pythonic Conventions and Standards

All Python code introduced or modified by agents **MUST** follow established Pythonic conventions and standards, including:

- **PEP 8**: Adhere to the Python Style Guide for consistent formatting, naming conventions, and code structure.
- **Readability**: Prioritize clear, concise, and self-documenting code.
- **Idiomatic Python**: Utilize Python's built-in features and common patterns effectively.
- **Type Hinting**: Use type hints for improved code clarity, maintainability, and static analysis.

### 8.3. TDD - Test Driven Development

**Test Driven Development (TDD) is a mandatory practice for all agents.** Every enhanced, changed, or added functionality **MUST** be covered by related, extensive tests. Agents are **NOT** allowed to introduce any changes that are not thoroughly covered by tests ensuring proper project maintenance.

The TDD cycle involves:

1. **Red**: Write a failing test case that defines a new function or an improvement to an existing function.
2. **Green**: Write the minimum amount of code necessary to make the test pass.
3. **Refactor**: Refactor the code to improve its design, readability, and maintainability, ensuring all tests still pass.

This approach guarantees:

- **Robustness**: New features are immediately validated.
- **Maintainability**: Changes are less likely to introduce regressions.
- **Clear Requirements**: Tests serve as executable specifications.
- **Improved Design**: TDD encourages modular and testable code.

### 8.4. Software Architecture Principles

Agents should employ the following software architecture principles:

#### 8.4.1. TDD (Test Driven Development)

(See section 8.3 for detailed explanation of TDD.)

#### 8.4.2. SOLID Principles

SOLID is an acronym for five design principles intended to make software designs more understandable, flexible, and maintainable. Agents **MUST** apply these principles:

- **S - Single Responsibility Principle (SRP)**: A class or module should have only one reason to change. This means it should have only one primary responsibility.
  - **How to follow**: Ensure each class, function, or module focuses on a single task. If a component has multiple responsibilities, consider splitting it.

- **O - Open/Closed Principle (OCP)**: Software entities (classes, modules, functions, etc.) should be open for extension, but closed for modification. This means new functionality should be added by extending existing code, not by altering it.
  - **How to follow**: Use interfaces, abstract classes, and polymorphism. Design components so that their behavior can be extended without changing their source code.

- **L - Liskov Substitution Principle (LSP)**: Subtypes must be substitutable for their base types without altering the correctness of the program. If `S` is a subtype of `T`, then objects of type `T` may be replaced with objects of type `S` without breaking the application.
  - **How to follow**: Ensure that derived classes can truly replace their base classes. Avoid breaking contracts (preconditions, postconditions, invariants) defined by the base class.

- **I - Interface Segregation Principle (ISP)**: Clients should not be forced to depend on interfaces they do not use. Rather than one large interface, many smaller, client-specific interfaces are better.
  - **How to follow**: Break down large interfaces into smaller, more specific ones. Clients should only implement or
depend on the methods they actually need.

- **D - Dependency Inversion Principle (DIP)**:
    1. High-level modules should not depend on low-level modules. Both should depend on abstractions.
    2. Abstractions should not depend on details. Details should depend on abstractions.
  - **How to follow**: Use dependency injection. Depend on interfaces or abstract classes rather than concrete implementations. This promotes flexibility and testability.

#### 8.4.3. KISS (Keep It Simple, Stupid)

Agents should always strive for simplicity in design and implementation.

- **How to follow**: Avoid unnecessary complexity. Choose the simplest solution that meets the requirements. Simple code is easier to understand, maintain, and debug.

#### 8.4.4. DRY (Don't Repeat Yourself)

Avoid duplicating code or knowledge within the system.

- **How to follow**: Identify and abstract common patterns or functionalities into reusable components (functions, classes, modules). If you find yourself writing the same code more than once, it's a candidate for abstraction.

### 8.5. Git Branch Structure

Agents **MUST** adhere to the project's Git branch structure to ensure stability and facilitate collaborative development:

- **`main`**: This branch contains stable, 100% test-passing code and is used for releases. Direct pull requests from external contributors to `main` are not allowed. Only project maintainers can merge into `main`.
- **`dev`**: This is the primary development branch. All contributors, including LLM agents, are expected to base their changes on this branch. To contribute, start by forking the repository, then create a new branch from `dev` for your changes, and submit your pull requests to the `dev` branch.
