import unittest
import json
import logging # Import logging
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock 
from sqlalchemy import MetaData 

from llm_accounting.backends.postgresql import PostgreSQLBackend
from llm_accounting.models import accounting, audit, limits 

MOCK_PG_CACHE_FILE_PATH = Path("tests/temp_test_data_pg_migrations/data/postgres_migration_status.json")
POSTGRES_BACKEND_LOGGER_NAME = 'llm_accounting.backends.postgresql' # Define logger name

class TestPostgreSQLMigrationsCache(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("tests/temp_test_data_pg_migrations")
        self.test_dir.mkdir(parents=True, exist_ok=True)

        self.controlled_cache_path = MOCK_PG_CACHE_FILE_PATH
        self.controlled_cache_dir = self.controlled_cache_path.parent

        if self.controlled_cache_path.exists(): self.controlled_cache_path.unlink()
        if self.controlled_cache_dir.exists(): shutil.rmtree(self.controlled_cache_dir)

        self.patcher_cache_path = patch('llm_accounting.backends.postgresql.POSTGRES_MIGRATION_CACHE_PATH', MOCK_PG_CACHE_FILE_PATH)
        self.patcher_create_engine = patch('llm_accounting.backends.postgresql.create_engine')
        self.patcher_inspect = patch('llm_accounting.backends.postgresql.inspect')
        self.patcher_base_metadata = patch('llm_accounting.backends.postgresql.Base.metadata', spec=MetaData)
        self.patcher_run_migrations = patch('llm_accounting.backends.postgresql.run_migrations')
        self.patcher_get_head_revision = patch('llm_accounting.backends.postgresql.get_head_revision')
        self.patcher_stamp_db_head = patch('llm_accounting.backends.postgresql.stamp_db_head')
        self.patcher_conn_manager = patch('llm_accounting.backends.postgresql.ConnectionManager')
        
        self.mock_cache_path = self.patcher_cache_path.start()
        self.mock_create_engine = self.patcher_create_engine.start()
        self.mock_inspect_sqlalchemy = self.patcher_inspect.start()
        self.mock_base_metadata = self.patcher_base_metadata.start() 
        self.mock_run_migrations = self.patcher_run_migrations.start()
        self.mock_get_head_revision = self.patcher_get_head_revision.start()
        self.mock_stamp_db_head = self.patcher_stamp_db_head.start()
        self.MockConnectionManager = self.patcher_conn_manager.start()

        self.mock_engine = MagicMock()
        self.mock_create_engine.return_value = self.mock_engine
        self.mock_inspector = MagicMock()
        self.mock_inspect_sqlalchemy.return_value = self.mock_inspector
        self.mock_conn_manager_instance = MagicMock()
        self.MockConnectionManager.return_value = self.mock_conn_manager_instance

        self.defined_model_table_names = {'accounting_entries', 'usage_limits', 'audit_log_entries'}
        self.model_table_names_with_alembic = self.defined_model_table_names.union({'alembic_version'})

        self.mock_sorted_tables_data = [MagicMock(name=name) for name in self.defined_model_table_names]
        for mt, name in zip(self.mock_sorted_tables_data, self.defined_model_table_names): mt.name = name
        
        self.mock_base_metadata.sorted_tables = self.mock_sorted_tables_data
        self.mock_base_metadata.create_all = MagicMock(name='Base.metadata.create_all')

        self.dummy_connection_string = "postgresql://user:pass@host:port/dbname"
        self.backend = PostgreSQLBackend(self.dummy_connection_string)

        # Ensure the specific logger is enabled for these tests
        logger_instance = logging.getLogger(POSTGRES_BACKEND_LOGGER_NAME)
        logger_instance.disabled = False
        logger_instance.setLevel(logging.INFO)

    def tearDown(self):
        self.patcher_cache_path.stop()
        self.patcher_create_engine.stop()
        self.patcher_inspect.stop()
        self.patcher_base_metadata.stop() 
        self.patcher_run_migrations.stop()
        self.patcher_get_head_revision.stop()
        self.patcher_stamp_db_head.stop()
        self.patcher_conn_manager.stop()
        if self.test_dir.exists(): shutil.rmtree(self.test_dir)

    def test_new_database_creates_schema_stamps_and_caches(self):
        self.mock_inspector.get_table_names.return_value = [] 
        stamped_rev = "pg_stamped_rev_test1"
        self.mock_stamp_db_head.return_value = stamped_rev
        
        self.backend.initialize()

        self.mock_create_engine.assert_called_once_with(self.dummy_connection_string, future=True)
        self.mock_inspect_sqlalchemy.assert_called_with(self.mock_engine) 
        self.mock_base_metadata.create_all.assert_called_once_with(self.mock_engine) 
        self.mock_stamp_db_head.assert_called_once_with(self.dummy_connection_string)
        self.mock_run_migrations.assert_not_called()
        self.assertTrue(self.controlled_cache_path.exists())
        with open(self.controlled_cache_path, 'r') as f: cache_data = json.load(f)
        self.assertEqual(cache_data.get("connection_string_hash"), hash(self.dummy_connection_string))
        self.assertEqual(cache_data.get("revision"), stamped_rev)

    def test_existing_db_cache_up_to_date_skips_migrations(self):
        self.mock_inspector.get_table_names.return_value = list(self.model_table_names_with_alembic)
        current_rev = "pg_head_rev_1"
        self.mock_get_head_revision.return_value = current_rev
        self.controlled_cache_dir.mkdir(parents=True, exist_ok=True)
        with open(self.controlled_cache_path, 'w') as f:
            json.dump({"connection_string_hash": hash(self.dummy_connection_string), "revision": current_rev}, f)
        
        with self.assertLogs(logger=POSTGRES_BACKEND_LOGGER_NAME, level='INFO') as cm:
            self.backend.initialize()

        self.assertTrue(len(cm.output) > 0, f"Expected INFO logs for PostgreSQL, but none were captured. Logger '{POSTGRES_BACKEND_LOGGER_NAME}' handlers: {logging.getLogger(POSTGRES_BACKEND_LOGGER_NAME).handlers}")

        expected_log_msg = f"Cached PostgreSQL revision {current_rev} matches head script revision. Migrations will be skipped."
        self.assertTrue(any(expected_log_msg in message for message in cm.output), f"Expected log '{expected_log_msg}' missing. Logs: {cm.output}")

        self.mock_run_migrations.assert_not_called()
        self.mock_stamp_db_head.assert_not_called()
        self.assertEqual(self.mock_inspector.get_table_names.call_count, 2) 
        self.mock_base_metadata.create_all.assert_not_called() 

    def test_existing_db_cache_outdated_runs_migrations(self):
        self.mock_inspector.get_table_names.return_value = list(self.model_table_names_with_alembic)
        old_rev = "pg_old_rev"
        new_head_rev = "pg_new_head_rev"
        self.mock_get_head_revision.return_value = new_head_rev
        self.mock_run_migrations.return_value = new_head_rev
        self.controlled_cache_dir.mkdir(parents=True, exist_ok=True)
        with open(self.controlled_cache_path, 'w') as f:
            json.dump({"connection_string_hash": hash(self.dummy_connection_string), "revision": old_rev}, f)

        self.backend.initialize()

        self.mock_run_migrations.assert_called_once_with(db_url=self.dummy_connection_string)
        self.mock_stamp_db_head.assert_not_called()
        self.assertTrue(self.controlled_cache_path.exists())
        with open(self.controlled_cache_path, 'r') as f: cache_data = json.load(f)
        self.assertEqual(cache_data.get("revision"), new_head_rev)
        self.mock_base_metadata.create_all.assert_not_called() 

    def test_existing_db_cache_missing_runs_migrations(self):
        self.mock_inspector.get_table_names.return_value = list(self.model_table_names_with_alembic)
        current_head_rev = "pg_head_rev_2"
        self.mock_get_head_revision.return_value = current_head_rev
        self.mock_run_migrations.return_value = current_head_rev

        self.backend.initialize()

        self.mock_run_migrations.assert_called_once_with(db_url=self.dummy_connection_string)
        self.mock_stamp_db_head.assert_not_called()
        self.assertTrue(self.controlled_cache_path.exists())
        with open(self.controlled_cache_path, 'r') as f: cache_data = json.load(f)
        self.assertEqual(cache_data.get("revision"), current_head_rev)
        self.mock_base_metadata.create_all.assert_not_called()

    def test_existing_db_cache_for_different_connection_string(self):
        self.mock_inspector.get_table_names.return_value = list(self.model_table_names_with_alembic)
        current_head_rev = "pg_current_head"
        self.mock_get_head_revision.return_value = current_head_rev
        self.mock_run_migrations.return_value = current_head_rev
        self.controlled_cache_dir.mkdir(parents=True, exist_ok=True)
        with open(self.controlled_cache_path, 'w') as f:
            json.dump({"connection_string_hash": hash("other_connection_string"), "revision": "pg_other_rev"}, f)
        
        self.backend.initialize()

        self.mock_run_migrations.assert_called_once_with(db_url=self.dummy_connection_string)
        self.assertTrue(self.controlled_cache_path.exists())
        with open(self.controlled_cache_path, 'r') as f: cache_data = json.load(f)
        self.assertEqual(cache_data.get("connection_string_hash"), hash(self.dummy_connection_string))
        self.assertEqual(cache_data.get("revision"), current_head_rev)
        self.mock_base_metadata.create_all.assert_not_called()

    def test_existing_db_migrated_but_model_table_missing_runs_create_all(self):
        self.assertTrue(self.defined_model_table_names, "Model table names should not be empty for this test.")
        
        missing_table_name = list(self.defined_model_table_names)[0]
        tables_returned_by_inspector_final = list(self.defined_model_table_names - {missing_table_name})

        self.mock_inspector.get_table_names.side_effect = [
            list(self.model_table_names_with_alembic),  
            tables_returned_by_inspector_final         
        ]
        
        current_rev = "pg_head_rev_ok"
        self.mock_get_head_revision.return_value = current_rev
        self.controlled_cache_dir.mkdir(parents=True, exist_ok=True)
        with open(self.controlled_cache_path, 'w') as f:
            json.dump({"connection_string_hash": hash(self.dummy_connection_string), "revision": current_rev}, f)

        self.backend.initialize()

        self.mock_run_migrations.assert_not_called() 
        self.mock_stamp_db_head.assert_not_called()
        self.mock_base_metadata.create_all.assert_called_once_with(self.mock_engine)

if __name__ == '__main__':
    unittest.main()
