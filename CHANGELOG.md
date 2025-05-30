## 2025-05-30 18:54:00 - Refactor: Migrate to Alembic-only schema management and bump version
**Commit:** `(will be filled by git)`
- Modified: `pyproject.toml` (version bump to 0.1.19)
- Modified: `pytest.ini` (removed python_paths)
- Modified: `src/llm_accounting/backends/postgresql.py` (migration timing and schema management)
- Modified: `src/llm_accounting/backends/sqlite.py` (Alembic migration integration)
- Modified: `src/llm_accounting/cli/main.py` (formatting fixes)

## 2025-05-29 16:11:00 - docs: Clarify Alembic and SQLAlchemy usage in README.md
**Commit:** `(will be filled by git)`
- Modified: `README.md` (clarified explanation of Alembic and SQLAlchemy interaction)

## 2025-05-29 16:05:00 - Refactor: Centralize database migration logic into db_migrations module
**Commit:** `(will be filled by git)`
- Added: `src/llm_accounting/db_migrations.py`
- Modified: `src/llm_accounting/__init__.py` (removed migration logic)
- Modified: `src/llm_accounting/backends/postgresql.py` (imported and called new migration function)
- Modified: `tests/test_migrations.py` (updated import path for migration function)

## 2025-05-29 14:14:00 - docs: Improve README.md clarity and fix custom backend example
**Commit:** `(will be filled by git)`
- Fixed: Broken CLI example for `llm-accounting select` in `README.md`.
- Removed: Duplicated "Database Migrations" section from `README.md`.
- Fixed: Incorrect method signatures in `MyCustomBackend` example in `README.md` by re-adding `self` parameter.

## 2025-05-29 12:21:15 - feat: Integrate database migrations (Alembic)
**Commit:** `(merged from feat/database-migrations)`
- Added: `alembic.ini`
- Added: `alembic/README`
- Added: `alembic/env.py`
- Added: `alembic/script.py.mako`
- Added: `alembic/versions/82f27c891782_initial_tables.py`
- Added: `alembic/versions/ba9718840e75_add_notes_to_accounting_entry.py`
- Added: `src/llm_accounting/models/accounting.py`
- Added: `src/llm_accounting/models/audit.py`
- Added: `tests/test_migrations.py`
- Modified: `src/llm_accounting/__init__.py` (automatic migration on init)
- Modified: `src/llm_accounting/backends/postgresql.py` (SQLAlchemy integration)
- Modified: `src/llm_accounting/backends/postgresql_backend_parts/schema_manager.py` (DDL removed)
- Modified: `src/llm_accounting/backends/sqlite.py` (SQLAlchemy integration)
- Modified: `src/llm_accounting/backends/sqlite_queries.py` (SQLAlchemy connection)
- Modified: `src/llm_accounting/backends/sqlite_utils.py` (DDL removed)
- Modified: `src/llm_accounting/models/__init__.py` (new models exposed)
- Modified: `tests/backends/postgresql_backend_tests/base_test_postgresql.py` (updated for new backend)
- Modified: `tests/backends/sqlite_backend_tests/test_sqlite_audit_log.py` (updated for new backend)
- Modified: `tests/cli/test_select/select/conftest.py` (in-memory SQLite fix)
- Modified: `tests/conftest.py` (migration setup)

## 2025-05-29 11:10:35 - refactor: Prevent CLI from running as privileged user
**Commit:** `(will be filled by git)`
- Modified: `pyproject.toml`
- Modified: `src/llm_accounting/cli/main.py`

# Changelog

## 2025-05-28 15:09:03 - Bump project version
**Commit:** `ccdb55c`
- Modified: `pyproject.toml`

## 2025-05-28 15:03:17 - feat: Enhance audit log documentation and schema for PostgreSQL
**Commit:** `6b05198`
- Modified: `README.md`
- Modified: `src/llm_accounting/backends/postgresql_backend_parts/schema_manager.py`

## 2025-05-28 11:36:51 - feat: Update version and refactor backend tests
**Commit:** `14a4675`
- Modified: `pyproject.toml`
- Added: `tests/backends/postgresql_backend_tests/__init__.py`
- Added: `tests/backends/postgresql_backend_tests/base_test_postgresql.py`
- Added: `tests/backends/postgresql_backend_tests/test_postgresql_audit_log.py`
- Added: `tests/backends/postgresql_backend_tests/test_postgresql_init_and_connection.py`
- Added: `tests/backends/postgresql_backend_tests/test_postgresql_query_delegation.py`
- Added: `tests/backends/postgresql_backend_tests/test_postgresql_query_execution.py`
- Added: `tests/backends/postgresql_backend_tests/test_postgresql_quota_accounting.py`
- Added: `tests/backends/postgresql_backend_tests/test_postgresql_usage_insertion.py`
- Added: `tests/backends/postgresql_backend_tests/test_postgresql_usage_limits.py`
- Added: `tests/backends/sqlite_backend_tests/conftest.py`
- Added: `tests/backends/sqlite_backend_tests/test_sqlite_audit_log.py`
- Added: `tests/backends/sqlite_backend_tests/test_sqlite_init_and_usage.py`
- Added: `tests/backends/sqlite_backend_tests/test_sqlite_stats_and_purge.py`
- Added: `tests/backends/sqlite_backend_tests/test_sqlite_usage_limits.py`
- Modified: `tests/backends/test_postgresql.py`
- Modified: `tests/backends/test_sqlite.py`

## 2025-05-28 11:01:27 - Replace Neon backend with PostgreSQL backend
**Commit:** `a932b04`
- Modified: `README.md`
- Renamed (91%): `src/llm_accounting/backends/neon.py` to `src/llm_accounting/backends/postgresql.py`
- Renamed (73%): `src/llm_accounting/backends/neon_backend_parts/connection_manager.py` to `src/llm_accounting/backends/postgresql_backend_parts/connection_manager.py`
- Renamed (100%): `src/llm_accounting/backends/neon_backend_parts/data_deleter.py` to `src/llm_accounting/backends/postgresql_backend_parts/data_deleter.py`
- Renamed (94%): `src/llm_accounting/backends/neon_backend_parts/data_inserter.py` to `src/llm_accounting/backends/postgresql_backend_parts/data_inserter.py`
- Renamed (100%): `src/llm_accounting/backends/neon_backend_parts/limit_manager.py` to `src/llm_accounting/backends/postgresql_backend_parts/limit_manager.py`
- Renamed (96%): `src/llm_accounting/backends/neon_backend_parts/query_executor.py` to `src/llm_accounting/backends/postgresql_backend_parts/query_executor.py`
- Renamed (100%): `src/llm_accounting/backends/neon_backend_parts/query_reader.py` to `src/llm_accounting/backends/postgresql_backend_parts/query_reader.py`
- Renamed (100%): `src/llm_accounting/backends/neon_backend_parts/quota_reader.py` to `src/llm_accounting/backends/postgresql_backend_parts/quota_reader.py`
- Renamed (100%): `src/llm_accounting/backends/neon_backend_parts/schema_manager.py` to `src/llm_accounting/backends/postgresql_backend_parts/schema_manager.py`
- Modified: `src/llm_accounting/cli/main.py`
- Modified: `src/llm_accounting/cli/utils.py`
- Renamed (91%): `tests/backends/test_neon.py` to `tests/backends/test_postgresql.py`
- Modified: `tests/cli/test_cli_stats.py`
- Modified: `tests/cli/test_select_project.py`

## 2025-05-28 10:41:08 - Fix: Resolve TestSQLiteAuditLog failures and improve audit log filtering
**Commit:** `00fa2ad`
- Modified: `src/llm_accounting/backends/sqlite.py`
- Modified: `src/llm_accounting/backends/sqlite_utils.py`
- Modified: `tests/api_compatibility/test_audit_logger_api.py`
- Modified: `tests/backends/mock_backends.py`
- Modified: `tests/backends/test_neon.py`
- Modified: `tests/backends/test_sqlite.py`
- Modified: `tests/cli/test_cli_stats.py`
- Modified: `tests/conftest.py`
- Modified: `tests/core/test_accounting_tracking.py`

## 2025-05-28 08:08:31 - Refactor: Make audit log use pluggable database backend
**Commit:** `20890f2`
- Modified: `src/llm_accounting/audit_log.py`
- Modified: `src/llm_accounting/backends/base.py`
- Modified: `src/llm_accounting/backends/neon.py`
- Modified: `src/llm_accounting/backends/neon_backend_parts/data_inserter.py`
- Modified: `src/llm_accounting/backends/neon_backend_parts/query_executor.py`
- Modified: `src/llm_accounting/backends/neon_backend_parts/schema_manager.py`
- Modified: `src/llm_accounting/backends/sqlite.py`
- Modified: `src/llm_accounting/backends/sqlite_utils.py`
- Modified: `tests/backends/test_neon.py`
- Modified: `tests/backends/test_sqlite.py`
- Modified: `tests/test_audit_log.py`

## 2025-05-27 22:51:06 - Properly expose all new parameters
**Commit:** `192bfb6`
- Modified: `README.md`
- Modified: `src/llm_accounting/__init__.py`
- Modified: `src/llm_accounting/backends/base.py`
- Modified: `src/llm_accounting/cli/main.py`
- Modified: `src/llm_accounting/cli/utils.py`

## 2025-05-27 17:17:19 - Fix README.md
**Commit:** `18baf03`
- Modified: `README.md`

## 2025-05-27 17:02:53 - Fix errors reported by linter.
**Commit:** `49f5c5f`
- Modified: `example.py`
- Modified: `src/llm_accounting/backends/neon_backend_parts/query_executor.py`

## 2025-05-27 16:48:04 - Fix errors reported by linter, rise package version
**Commit:** `e5e4ceb`
- Modified: `pyproject.toml`
- Modified: `src/llm_accounting/backends/mock_backend_parts/usage_manager.py`
- Modified: `src/llm_accounting/backends/neon.py`
- Modified: `src/llm_accounting/backends/neon_backend_parts/connection_manager.py`
- Modified: `src/llm_accounting/backends/neon_backend_parts/data_inserter.py`
- Modified: `src/llm_accounting/backends/neon_backend_parts/limit_manager.py`
- Modified: `src/llm_accounting/backends/sqlite.py`
- Modified: `src/llm_accounting/cli/commands/limits.py`
- Modified: `src/llm_accounting/models/__init__.py`
- Modified: `tests/backends/test_sqlite.py`

## 2025-05-27 16:28:12 - Fix linter errors
**Commit:** `5a03473`
- Modified: `src/llm_accounting/audit_log.py`
- Modified: `src/llm_accounting/backends/base.py`
- Modified: `src/llm_accounting/backends/mock_backend.py`
- Added: `src/llm_accounting/backends/mock_backend_parts/connection_manager.py`
- Added: `src/llm_accounting/backends/mock_backend_parts/limit_manager.py`
- Added: `src/llm_accounting/backends/mock_backend_parts/query_executor.py`
- Added: `src/llm_accounting/backends/mock_backend_parts/stats_manager.py`
- Added: `src/llm_accounting/backends/mock_backend_parts/usage_manager.py`
- Deleted: `src/llm_accounting/cli_old.py`

## 2025-05-27 14:46:56 - feat: Fix est_select_project.py and update README for project field
**Commit:** `4cbf435`
- Modified: `README.md`
- Modified: `src/llm_accounting/services/quota_service.py`
- Modified: `tests/accounting/test_global_limits.py`
- Modified: `tests/accounting/test_model_limits.py`
- Modified: `tests/accounting/test_multiple_limit_types.py`
- Modified: `tests/accounting/test_user_caller_limits.py`
- Modified: `tests/backends/test_neon.py`
- Modified: `tests/cli/test_cli_limits_project.py`
- Modified: `tests/cli/test_cli_tail.py`
- Modified: `tests/cli/test_select_project.py`
- Modified: `tests/core/test_project_quota_service.py`

## 2025-05-27 14:15:44 - Fix UTC
**Commit:** `72ec416`
- Modified: `tests/backends/test_sqlite.py`

## 2025-05-27 11:15:50 - Refactor: Decouple SQLAlchemy models from public API
**Commit:** `6077f25`
- Modified: `src/llm_accounting/__init__.py`
- Modified: `src/llm_accounting/backends/base.py`
- Modified: `src/llm_accounting/backends/mock_backend.py`
- Modified: `src/llm_accounting/backends/neon.py`
- Modified: `src/llm_accounting/backends/neon_backend_parts/limit_manager.py`
- Modified: `src/llm_accounting/backends/sqlite.py`
- Modified: `src/llm_accounting/backends/sqlite_utils.py`
- Modified: `src/llm_accounting/cli/commands/limits.py`
- Modified: `src/llm_accounting/models/limits.py`
- Modified: `src/llm_accounting/services/quota_service.py`
- Modified: `tests/accounting/test_global_limits.py`
- Modified: `tests/accounting/test_model_limits.py`
- Modified: `tests/accounting/test_multiple_limit_types.py`
- Modified: `tests/accounting/test_user_caller_limits.py`
- Modified: `tests/api_compatibility/test_llm_accounting_api.py`
- Modified: `tests/backends/mock_backends.py`
- Modified: `tests/backends/test_neon.py`
- Modified: `tests/backends/test_sqlite.py`
- Modified: `tests/core/test_quota_service.py`

## 2025-05-26 21:36:53 - Rise version in pyproject.toml to upload build with fixed dependencies
**Commit:** `dd6c342`
- Modified: `pyproject.toml`

## 2025-05-26 21:31:38 - Fix dependencies
**Commit:** `8ce0061`
- Modified: `pyproject.toml`

## 2025-05-26 15:53:42 - feat: Add project-based QuotaService and limit management
**Commit:** `f98e0cd`
- Modified: `src/llm_accounting/__init__.py`
- Modified: `src/llm_accounting/audit_log.py`
- Modified: `src/llm_accounting/backends/base.py`
- Modified: `src/llm_accounting/backends/mock_backend.py`
- Modified: `src/llm_accounting/backends/neon.py`
- Modified: `src/llm_accounting/backends/neon_backend_parts/data_inserter.py`
- Modified: `src/llm_accounting/backends/neon_backend_parts/query_reader.py`
- Modified: `src/llm_accounting/backends/neon_backend_parts/schema_manager.py`
- Modified: `src/llm_accounting/backends/sqlite.py`
- Modified: `src/llm_accounting/backends/sqlite_queries.py`
- Modified: `src/llm_accounting/backends/sqlite_utils.py`
- Modified: `src/llm_accounting/cli/commands/limits.py`
- Modified: `src/llm_accounting/cli/commands/select.py`
- Modified: `src/llm_accounting/cli/commands/tail.py`
- Modified: `src/llm_accounting/cli/commands/track.py`
- Modified: `src/llm_accounting/cli/parsers.py`
- Modified: `src/llm_accounting/models/limits.py`
- Modified: `src/llm_accounting/services/quota_service.py`
- Modified: `tests/backends/mock_backends.py`
- Modified: `tests/backends/test_sqlite.py`
- Added: `tests/cli/test_cli_limits_project.py`
- Modified: `tests/cli/test_cli_tail.py`
- Modified: `tests/cli/test_cli_track.py`
- Modified: `tests/cli/test_select/select/test_non_select_query.py`
- Added: `tests/cli/test_select_project.py`
- Added: `tests/core/test_project_quota_service.py`
- Modified: `tests/test_audit_log.py`

## 2025-05-23 20:36:20 - feat: Improve database connection management and backend abstraction
**Commit:** `2e7c4c6`
- Modified: `README.md`
- Modified: `pyproject.toml`
- Modified: `src/llm_accounting/backends/neon.py`
- Added: `src/llm_accounting/backends/neon_backend_parts/connection_manager.py`
- Added: `src/llm_accounting/backends/neon_backend_parts/data_deleter.py`
- Added: `src/llm_accounting/backends/neon_backend_parts/data_inserter.py`
- Added: `src/llm_accounting/backends/neon_backend_parts/limit_manager.py`
- Added: `src/llm_accounting/backends/neon_backend_parts/query_executor.py`
- Added: `src/llm_accounting/backends/neon_backend_parts/query_reader.py`
- Added: `src/llm_accounting/backends/neon_backend_parts/quota_reader.py`
- Added: `src/llm_accounting/backends/neon_backend_parts/schema_manager.py`
- Modified: `tests/backends/test_neon.py`

## 2025-05-23 19:58:16 - Fix problems reported by linter in neon.py
**Commit:** `e4a5ede`
- Modified: `src/llm_accounting/backends/neon.py`

## 2025-05-23 19:54:58 - Properly encapsulate database backends
**Commit:** `b06ed2d`
- Modified: `src/llm_accounting/__init__.py`
- Modified: `src/llm_accounting/backends/base.py`
- Modified: `src/llm_accounting/backends/mock_backend.py`
- Modified: `src/llm_accounting/backends/neon.py`
- Modified: `src/llm_accounting/backends/sqlite.py`
- Modified: `tests/backends/mock_backends.py`

## 2025-05-23 19:10:07 - Update pyproject.toml
**Commit:** `db3644e`
- Modified: `pyproject.toml`

## 2025-05-23 19:06:18 - Expose db filename, improve README
**Commit:** `b5b826c`
- Modified: `README.md`
- Added: `example.py`
- Modified: `src/llm_accounting/__init__.py`
- Modified: `src/llm_accounting/audit_log.py`

## 2025-05-23 17:50:47 - Fixing the README
**Commit:** `aaf3a64`
- Modified: `README.md`

## 2025-05-23 17:34:40 - Fix PyPI build
**Commit:** `1946778`
- Modified: `pyproject.toml`
- Modified: `requirements.txt`

## 2025-05-23 17:17:28 - Remove api_requests DB table
**Commit:** `73a6b65`
- Modified: `README.md`
- Modified: `src/llm_accounting/__init__.py`
- Modified: `src/llm_accounting/backends/base.py`
- Modified: `src/llm_accounting/backends/neon.py`
- Modified: `src/llm_accounting/backends/sqlite.py`
- Modified: `src/llm_accounting/backends/sqlite_queries.py`
- Modified: `src/llm_accounting/backends/sqlite_utils.py`
- Modified: `src/llm_accounting/models/__init__.py`
- Deleted: `src/llm_accounting/models/request.py`
- Modified: `src/llm_accounting/services/quota_service.py`
- Modified: `tests/api_compatibility/test_llm_accounting_api.py`
- Modified: `tests/backends/mock_backends.py`
- Modified: `tests/backends/test_neon.py`
- Modified: `tests/backends/test_sqlite.py`
- Modified: `tests/cli/test_select/select/conftest.py`

## 2025-05-23 15:18:17 - Update gitignore
**Commit:** `d97e76e`
- Modified: `.gitignore`

## 2025-05-23 13:16:40 - Fix pyproject
**Commit:** `c987e14`
- Modified: `pyproject.toml`

## 2025-05-23 13:14:00 - Fix pytest.ini to remove depreciation warning
**Commit:** `a78f9b1`
- Modified: `pytest.ini`

## 2025-05-23 13:12:19 - Add --version to the CLI
**Commit:** `eb757d7`
- Modified: `pyproject.toml`
- Modified: `src/llm_accounting/cli/main.py`
- Added: `tests/cli/test_cli_version.py`

## 2025-05-23 13:00:23 - Remove too strict, not crucial, failing tests
**Commit:** `5f49761`
- Modified: `tests/api_compatibility/test_cli_api.py`
- Modified: `tests/cli/test_select/select/test_output_formatting.py`

## 2025-05-23 10:41:18 - Add API backward compatibility tests
**Commit:** `9456514`
- Modified: `pytest.ini`
- Added: `tests/api_compatibility/test_audit_logger_api.py`
- Added: `tests/api_compatibility/test_cli_api.py`
- Added: `tests/api_compatibility/test_llm_accounting_api.py`
- Modified: `tests/cli/test_select/select/test_output_formatting.py`

## 2025-05-23 00:19:43 - Project version: 0.1.1
**Commit:** `f49efe4`
- Modified: `pyproject.toml`

## 2025-05-23 00:13:38 - Expose limits API via CLI, update README.md
**Commit:** `7dd0ec1`
- Modified: `README.md`
- Modified: `src/llm_accounting/__init__.py`
- Modified: `src/llm_accounting/backends/base.py`
- Modified: `src/llm_accounting/backends/neon.py`
- Modified: `src/llm_accounting/backends/sqlite.py`
- Added: `src/llm_accounting/cli/commands/limits.py`
- Modified: `src/llm_accounting/cli/main.py`
- Modified: `src/llm_accounting/cli/parsers.py`
- Modified: `src/llm_accounting/models/limits.py`
- Modified: `tests/backends/mock_backends.py`
- Modified: `tests/backends/test_neon.py`

## 2025-05-22 22:59:56 - Expose Neon DB backend via CLI, update readme and tests
**Commit:** `2093ca2`
- Modified: `README.md`
- Modified: `src/llm_accounting/cli/main.py`
- Modified: `src/llm_accounting/cli/utils.py`
- Modified: `tests/cli/test_cli_stats.py`

## 2025-05-22 22:48:38 - Add Neon DB backend
**Commit:** `6de9855`
- Modified: `.gitignore`
- Modified: `README.md`
- Modified: `pyproject.toml`
- Modified: `pytest.ini`
- Modified: `requirements.txt`
- Modified: `src/llm_accounting/__init__.py`
- Modified: `src/llm_accounting/backends/base.py`
- Added: `src/llm_accounting/backends/neon.py`
- Modified: `src/llm_accounting/backends/sqlite.py`
- Deleted: `src/llm_accounting/cli/commands/limits.py`
- Modified: `src/llm_accounting/cli/commands/select.py`
- Modified: `src/llm_accounting/cli/main.py`
- Modified: `src/llm_accounting/cli/parsers.py`
- Modified: `src/llm_accounting/models/__init__.py`
- Modified: `src/llm_accounting/models/limits.py`
- Modified: `src/llm_accounting/models/request.py`
- Modified: `src/llm_accounting/services/quota_service.py`
- Modified: `tests/accounting/test_global_limits.py`
- Modified: `tests/accounting/test_model_limits.py`
- Modified: `tests/accounting/test_multiple_limit_types.py`
- Modified: `tests/accounting/test_user_caller_limits.py`
- Modified: `tests/backends/mock_backends.py`
- Added: `tests/backends/test_neon.py`
- Modified: `tests/backends/test_sqlite.py`
- Deleted: `tests/cli/test_cli_limits.py`
- Modified: `tests/cli/test_select/select/test_aggregation.py`
- Modified: `tests/cli/test_select/select/test_basic_query.py`
- Modified: `tests/cli/test_select/select/test_no_results.py`
- Modified: `tests/cli/test_select/select/test_non_select_query.py`
- Modified: `tests/cli/test_select/select/test_output_formatting.py`
- Modified: `tests/cli/test_select/select/test_syntax_error.py`
- Modified: `tests/conftest.py`
- Modified: `tests/core/test_quota_service.py`

## 2025-05-22 20:00:48 - Ignore ruff cache
**Commit:** `1108720`
- Modified: `.gitignore`

## 2025-05-22 19:50:09 - Refactor audit logging system with timezone-aware timestamps and update test cases
**Commit:** `67e8601`
- Modified: `.gitignore`
- Modified: `src/llm_accounting/__init__.py`
- Modified: `src/llm_accounting/audit_log.py`
- Modified: `src/llm_accounting/models/__init__.py`
- Modified: `src/llm_accounting/models/limits.py`
- Modified: `tests/test_audit_log.py`

## 2025-05-22 16:00:14 - Refactor SQLite backend session handling and improve test coverage
**Commit:** `6be8f89`
- Modified: `src/llm_accounting/__init__.py`
- Modified: `src/llm_accounting/backends/base.py`
- Modified: `src/llm_accounting/backends/sqlite.py`
- Modified: `src/llm_accounting/cli/commands/select.py`
- Modified: `src/llm_accounting/services/quota_service.py`
- Modified: `tests/accounting/test_global_limits.py`
- Modified: `tests/accounting/test_model_limits.py`
- Modified: `tests/accounting/test_multiple_limit_types.py`
- Modified: `tests/accounting/test_user_caller_limits.py`
- Modified: `tests/backends/mock_backends.py`
- Modified: `tests/cli/test_select/select/test_aggregation.py`
- Modified: `tests/cli/test_select/select/test_basic_query.py`
- Modified: `tests/cli/test_select/select/test_no_results.py`
- Modified: `tests/cli/test_select/select/test_non_select_query.py`
- Modified: `tests/cli/test_select/select/test_output_formatting.py`
- Modified: `tests/cli/test_select/select/test_syntax_error.py`
- Modified: `tests/core/test_quota_service.py`

## 2025-05-22 12:56:25 - Expose limits API in CLI, fix tests and linter issues
**Commit:** `5609060`
- Modified: `.gitignore`
- Modified: `pyproject.toml`
- Modified: `src/llm_accounting/__init__.py`
- Modified: `src/llm_accounting/backends/base.py`
- Modified: `src/llm_accounting/backends/sqlite.py`
- Modified: `src/llm_accounting/cli/commands/select.py`
- Modified: `src/llm_accounting/cli/main.py`
- Modified: `src/llm_accounting/cli/parsers.py`
- Modified: `src/llm_accounting/models/limits.py`
- Added: `tests/cli/test_cli_limits.py`

## 2025-05-22 12:17:57 - Add model column to CLI limits output and fix test
**Commit:** `41aadc6`
- Added: `src/llm_accounting/cli/commands/limits.py`

## 2025-05-22 09:20:58 - feat: Add audit log functionality
**Commit:** `be1b6d6`
- Modified: `src/llm_accounting/__init__.py`
- Added: `src/llm_accounting/audit_log.py`
- Added: `tests/test_audit_log.py`

## 2025-05-22 10:56:42 - Untrack local files
**Commit:** `e9b72bd`
- Deleted: `docs/flake8_output.txt`

## 2025-05-22 10:53:36 - Untrack local files
**Commit:** `6abbb2e`
- Deleted: `.clineignore`
- Deleted: `.clinerules/workflows/context.md`
- Deleted: `.clinerules/workflows/fix.md`
- Deleted: `.clinerules/workflows/make-modular.md`

## 2025-05-22 10:43:01 - Cleanup
**Commit:** `4433bb0`
- Deleted: `custom_test_db.sqlite`

## 2025-05-22 10:25:57 - Fix README.md to reflect latest changes
**Commit:** `f7651cc`
- Modified: `README.md`

## 2025-05-22 00:15:41 - Fix mock_backends
**Commit:** `0ce78e6`
- Modified: `tests/backends/mock_backends.py`

## 2025-05-21 23:46:24 - Fix linter errors
**Commit:** `364e494`
- Added: `.flake8`
- Modified: `setup.py`
- Modified: `src/llm_accounting/models/__init__.py`
- Modified: `src/llm_accounting/models/request.py`
- Modified: `tests/accounting/test_global_limits.py`
- Modified: `tests/accounting/test_model_limits.py`
- Modified: `tests/accounting/test_user_caller_limits.py`

## 2025-05-21 23:34:05 - Fix errors reported by linter
**Commit:** `82aec05`
- Modified: `.clineignore`
- Modified: `tests/accounting/test_global_limits.py`
- Modified: `tests/accounting/test_model_limits.py`
- Modified: `tests/accounting/test_multiple_limit_types.py`
- Modified: `tests/accounting/test_user_caller_limits.py`
- Modified: `tests/backends/mock_backends.py`
- Modified: `tests/backends/test_base.py`
- Modified: `tests/backends/test_sqlite.py`
- Modified: `tests/backends/test_usage_models.py`
- Modified: `tests/cli/test_cli_purge.py`
- Modified: `tests/cli/test_cli_stats.py`
- Modified: `tests/cli/test_cli_tail.py`
- Modified: `tests/cli/test_cli_track.py`
- Modified: `tests/cli/test_select/select/conftest.py`
- Modified: `tests/cli/test_select/select/test_aggregation.py`
- Modified: `tests/cli/test_select/select/test_basic_query.py`
- Modified: `tests/cli/test_select/select/test_no_results.py`
- Modified: `tests/cli/test_select/select/test_non_select_query.py`
- Modified: `tests/cli/test_select/select/test_output_formatting.py`
- Modified: `tests/cli/test_select/select/test_syntax_error.py`
- Modified: `tests/conftest.py`
- Modified: `tests/core/test_accounting_purge.py`
- Modified: `tests/core/test_accounting_stats.py`
- Modified: `tests/core/test_accounting_tracking.py`
- Modified: `tests/core/test_accounting_validation.py`
- Modified: `tests/core/test_quota_service.py`

## 2025-05-21 23:05:23 - Fix missing Base import in models/__init__.py to resolve test_quota_service.py failure
**Commit:** `3329701`
- Modified: `src/llm_accounting/models/__init__.py`

## 2025-05-21 23:00:29 - Small fixes to improve code quality and consistency.
**Commit:** `a56a5de`
- Added: `.clinerules/workflows/fix.md`
- Modified: `src/llm_accounting/__init__.py`
- Modified: `src/llm_accounting/backends/base.py`
- Modified: `src/llm_accounting/backends/sqlite.py`
