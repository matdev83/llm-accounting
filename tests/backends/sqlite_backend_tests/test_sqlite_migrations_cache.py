import unittest
import json
import logging
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from llm_accounting.backends.sqlite import SQLiteBackend

MOCK_CACHE_FILE_FULL_PATH_FOR_PATCHING = Path("tests/temp_test_data_migrations/data/migration_status.json")

# Get specific logger instance that will be used by the backend
SQLITE_BACKEND_LOGGER_NAME = 'llm_accounting.backends.sqlite'
CONNECTION_MANAGER_LOGGER_NAME = 'llm_accounting.backends.sqlite_backend_parts.connection_manager'

class TestSQLiteMigrationCache(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("tests/temp_test_data_migrations")
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.mock_db_name = "test_accounting.sqlite"
        self.mock_db_path = self.test_dir / self.mock_db_name
        self.controlled_cache_path = MOCK_CACHE_FILE_FULL_PATH_FOR_PATCHING
        self.controlled_cache_dir = self.controlled_cache_path.parent

        if self.mock_db_path.exists(): self.mock_db_path.unlink()
        if self.controlled_cache_path.exists(): self.controlled_cache_path.unlink()
        if self.controlled_cache_dir.exists():
            if not any(self.controlled_cache_dir.iterdir()):
                self.controlled_cache_dir.rmdir()
            else:
                shutil.rmtree(self.controlled_cache_dir)
        
        self.backend = None 

        # Ensure the specific logger is enabled for these tests
        # This is to counteract potential global logging state changes from other tests
        logger_instance = logging.getLogger(SQLITE_BACKEND_LOGGER_NAME)
        logger_instance.disabled = False
        logger_instance.setLevel(logging.INFO)
        
        # Ensure connection_manager's logger is also enabled for testing
        connection_manager_logger_instance = logging.getLogger(CONNECTION_MANAGER_LOGGER_NAME)
        connection_manager_logger_instance.disabled = False
        connection_manager_logger_instance.setLevel(logging.INFO)

        # Clear existing handlers that might be misconfigured by other tests,
        # assertLogs will add its own.
        # for handler in list(logger_instance.handlers): # Be careful with modifying handlers globally
        #     logger_instance.removeHandler(handler)


    def tearDown(self):
        if hasattr(self, 'backend') and self.backend:
            try:
                self.backend.close()
                # The engine is now managed by connection_manager
                if self.backend.connection_manager.engine:
                    self.backend.connection_manager.engine.dispose()
            except Exception as e:
                logging.error(f"Error closing or disposing backend in tearDown: {e}")
        
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    @patch('llm_accounting.backends.sqlite_backend_parts.connection_manager.Base.metadata.create_all')
    @patch('llm_accounting.backends.sqlite_backend_parts.connection_manager.get_head_revision')
    @patch('llm_accounting.backends.sqlite_backend_parts.connection_manager.run_migrations') 
    @patch('llm_accounting.backends.sqlite_backend_parts.connection_manager.update_migration_cache_after_success')
    @patch('llm_accounting.backends.sqlite_backend_parts.connection_manager.MIGRATION_CACHE_PATH', new=MOCK_CACHE_FILE_FULL_PATH_FOR_PATCHING)
    def test_new_database_creates_schema_stamps_and_caches(self, mock_update_cache, mock_run_migrations_upgrade, mock_get_head_revision, mock_create_all):
        stamped_rev = "stamped_head_rev_123"
        mock_run_migrations_upgrade.return_value = stamped_rev
        
        self.backend = SQLiteBackend(db_path=str(self.mock_db_path)) 
        self.backend.initialize()

        mock_create_all.assert_not_called()
        mock_run_migrations_upgrade.assert_called_once()
        mock_update_cache.assert_called_once_with(MOCK_CACHE_FILE_FULL_PATH_FOR_PATCHING, stamped_rev)

    @patch('llm_accounting.backends.sqlite_backend_parts.connection_manager.Base.metadata.create_all')
    @patch('llm_accounting.backends.sqlite_backend_parts.connection_manager.get_head_revision')
    @patch('llm_accounting.backends.sqlite_backend_parts.connection_manager.run_migrations')
    @patch('llm_accounting.backends.sqlite_backend_parts.connection_manager.should_run_migrations')
    @patch('llm_accounting.backends.sqlite_backend_parts.connection_manager.MIGRATION_CACHE_PATH', new=MOCK_CACHE_FILE_FULL_PATH_FOR_PATCHING)
    def test_existing_db_cache_up_to_date(self, mock_should_run_migrations, mock_run_migrations, mock_get_head_revision, mock_create_all):
        self.mock_db_path.write_text("dummy db content") 
        current_rev = "head_rev_abc"

        mock_get_head_revision.return_value = current_rev
        mock_should_run_migrations.return_value = False  # Cache is up to date
        
        self.backend = SQLiteBackend(db_path=str(self.mock_db_path)) 
        with self.assertLogs(logger=CONNECTION_MANAGER_LOGGER_NAME, level='DEBUG') as cm:
            self.backend.initialize()
        
        self.assertTrue(len(cm.output) > 0, f"Expected DEBUG logs for SQLite, but none were captured. Logger '{CONNECTION_MANAGER_LOGGER_NAME}' handlers: {logging.getLogger(CONNECTION_MANAGER_LOGGER_NAME).handlers}")
        
        expected_log_msg = f"Migrations skipped for {self.mock_db_path} based on package version cache."
        self.assertTrue(any(expected_log_msg in message for message in cm.output), f"Expected log '{expected_log_msg}' missing. Logs: {cm.output}")

        mock_run_migrations.assert_not_called()
        mock_create_all.assert_not_called()


    @patch('llm_accounting.backends.sqlite_backend_parts.connection_manager.Base.metadata.create_all')
    @patch('llm_accounting.backends.sqlite_backend_parts.connection_manager.get_head_revision')
    @patch('llm_accounting.backends.sqlite_backend_parts.connection_manager.run_migrations')
    @patch('llm_accounting.backends.sqlite_backend_parts.connection_manager.should_run_migrations')
    @patch('llm_accounting.backends.sqlite_backend_parts.connection_manager.update_migration_cache_after_success')
    @patch('llm_accounting.backends.sqlite_backend_parts.connection_manager.MIGRATION_CACHE_PATH', new=MOCK_CACHE_FILE_FULL_PATH_FOR_PATCHING)
    def test_existing_db_cache_outdated(self, mock_update_cache, mock_should_run_migrations, mock_run_migrations, mock_get_head_revision, mock_create_all):
        self.mock_db_path.write_text("dummy db content")
        new_rev_from_scripts = "new_rev_2_scripts"
        new_rev_from_migration = "new_rev_2_migrated" 

        mock_get_head_revision.return_value = new_rev_from_scripts
        mock_should_run_migrations.return_value = True  # Cache is outdated
        mock_run_migrations.return_value = new_rev_from_migration

        self.backend = SQLiteBackend(db_path=str(self.mock_db_path)) 
        self.backend.initialize()

        mock_run_migrations.assert_called_once()
        mock_create_all.assert_not_called() 
        mock_update_cache.assert_called_once_with(MOCK_CACHE_FILE_FULL_PATH_FOR_PATCHING, new_rev_from_migration)

    @patch('llm_accounting.backends.sqlite_backend_parts.connection_manager.Base.metadata.create_all')
    @patch('llm_accounting.backends.sqlite_backend_parts.connection_manager.get_head_revision')
    @patch('llm_accounting.backends.sqlite_backend_parts.connection_manager.run_migrations')
    @patch('llm_accounting.backends.sqlite_backend_parts.connection_manager.should_run_migrations')
    @patch('llm_accounting.backends.sqlite_backend_parts.connection_manager.update_migration_cache_after_success')
    @patch('llm_accounting.backends.sqlite_backend_parts.connection_manager.MIGRATION_CACHE_PATH', new=MOCK_CACHE_FILE_FULL_PATH_FOR_PATCHING)
    def test_existing_db_cache_missing(self, mock_update_cache, mock_should_run_migrations, mock_run_migrations, mock_get_head_revision, mock_create_all):
        self.mock_db_path.write_text("dummy db content") 

        head_rev_scripts = "head_rev_3_scripts"
        migrated_rev = "migrated_rev_3"
        mock_get_head_revision.return_value = head_rev_scripts
        mock_should_run_migrations.return_value = True  # Cache is missing
        mock_run_migrations.return_value = migrated_rev

        self.backend = SQLiteBackend(db_path=str(self.mock_db_path)) 
        self.backend.initialize()

        mock_run_migrations.assert_called_once()
        mock_create_all.assert_not_called()
        mock_update_cache.assert_called_once_with(MOCK_CACHE_FILE_FULL_PATH_FOR_PATCHING, migrated_rev)

    @patch('llm_accounting.backends.sqlite_backend_parts.connection_manager.Base.metadata.create_all')
    @patch('llm_accounting.backends.sqlite_backend_parts.connection_manager.get_head_revision')
    @patch('llm_accounting.backends.sqlite_backend_parts.connection_manager.run_migrations') 
    @patch('llm_accounting.backends.sqlite_backend_parts.connection_manager.MIGRATION_CACHE_PATH', new=MOCK_CACHE_FILE_FULL_PATH_FOR_PATCHING)
    def test_in_memory_database(self, mock_run_migrations_upgrade, mock_get_head_revision, mock_create_all):
        if self.controlled_cache_path.exists(): self.controlled_cache_path.unlink()
        
        mock_run_migrations_upgrade.return_value = "in_memory_migrated_rev"

        self.backend = SQLiteBackend(db_path=":memory:") 
        self.backend.initialize()

        mock_run_migrations_upgrade.assert_not_called() # Changed to assert_not_called()
        mock_create_all.assert_called_once()
        mock_get_head_revision.assert_not_called()
        self.assertFalse(self.controlled_cache_path.exists())

if __name__ == '__main__':
    unittest.main()
