import unittest
from unittest.mock import patch, MagicMock, call
import os
from datetime import datetime

# Assuming src is in PYTHONPATH or the tests are run in a way that src can be found
from src.llm_accounting.backends.neon import NeonBackend
from src.llm_accounting.backends.base import UsageEntry, UsageStats
from src.llm_accounting.models.request import APIRequest
from src.llm_accounting.models.limits import UsageLimit, LimitScope, LimitType, TimeInterval

# Import psycopg2 and its error types for mocking side effects
import psycopg2 # Keep this for type hinting and raising psycopg2.Error
# We will mock psycopg2 where it's used in neon.py, so direct use here is for reference/type.


class TestNeonBackend(unittest.TestCase):

    def setUp(self):
        # Patch psycopg2 module globally for the duration of the test
        self.patcher = patch('src.llm_accounting.backends.neon.psycopg2')
        self.mock_psycopg2_module = self.patcher.start()

        # Create a mock for psycopg2.Error that inherits from Exception
        # This is crucial for `except psycopg2.Error` to work correctly with the mock
        class MockPsycopg2Error(Exception):
            pass
        self.mock_psycopg2_module.Error = MockPsycopg2Error
        self.mock_psycopg2_module.OperationalError = MockPsycopg2Error # Often OperationalError is caught too

        # Set dummy environment variable
        self.original_neon_conn_string = os.environ.get('NEON_CONNECTION_STRING')
        os.environ['NEON_CONNECTION_STRING'] = 'dummy_dsn_from_env'

        # Instantiate the backend
        self.backend = NeonBackend()

        # Mock the connection and cursor objects
        self.mock_conn = self.mock_psycopg2_module.connect.return_value
        self.mock_cursor = self.mock_conn.cursor.return_value.__enter__.return_value

        # Explicitly set the 'closed' attribute for the mock connection
        self.mock_conn.closed = False # Connection is initially open

    def tearDown(self):
        # Stop the patcher
        self.patcher.stop()

        # Explicitly close the mock connection if it exists and is not already closed
        if self.backend.conn and not self.backend.conn.closed:
            self.backend.conn.close()

        # Restore original environment variable
        if self.original_neon_conn_string is None:
            if 'NEON_CONNECTION_STRING' in os.environ:
                del os.environ['NEON_CONNECTION_STRING']
        else:
            os.environ['NEON_CONNECTION_STRING'] = self.original_neon_conn_string

    # Test methods will be added here

    def test_init_success(self):
        # Test with connection string from environment
        self.assertEqual(self.backend.connection_string, 'dummy_dsn_from_env')
        self.assertIsNone(self.backend.conn)

        # Test with connection string as argument
        backend_with_arg = NeonBackend(neon_connection_string='dummy_dsn_from_arg')
        self.assertEqual(backend_with_arg.connection_string, 'dummy_dsn_from_arg')
        self.assertIsNone(backend_with_arg.conn)

    @patch.dict(os.environ, {}, clear=True) # Temporarily clear environment variables
    def test_init_missing_connection_string(self):
        # Unset the one we might have set in setUp for the global self.backend
        if 'NEON_CONNECTION_STRING' in os.environ:
             del os.environ['NEON_CONNECTION_STRING']
        
        with self.assertRaisesRegex(ValueError, "Neon connection string not provided"):
            NeonBackend()

    def test_initialize_success(self):
        # Mock _create_tables to avoid testing its DDL execution here
        self.backend._create_tables = MagicMock(name="_create_tables_mock_on_instance")

        self.backend.initialize()

        self.mock_psycopg2_module.connect.assert_called_once_with('dummy_dsn_from_env')
        self.assertEqual(self.backend.conn, self.mock_conn)
        self.backend._create_tables.assert_called_once()


    def test_initialize_connection_error(self):
        self.mock_psycopg2_module.connect.side_effect = self.mock_psycopg2_module.Error("Connection failed")
        
        with self.assertRaisesRegex(ConnectionError, r"Failed to connect to Neon/PostgreSQL database \(see logs for details\)\."):
            self.backend.initialize()
        self.assertIsNone(self.backend.conn)

    def test_close_connection(self):
        # 1. Initialize to get a connection
        # We need to make sure _create_tables doesn't fail during initialize
        self.backend._create_tables = MagicMock()
        self.backend.initialize()
        self.assertEqual(self.backend.conn, self.mock_conn)

        # 2. Close the connection
        self.backend.close()
        self.mock_conn.close.assert_called_once()
        self.assertIsNone(self.backend.conn)
        self.mock_conn.closed = True # Simulate the connection being closed

        # 3. Test closing when already closed (no error, close not called again)
        self.mock_conn.close.reset_mock() # Reset call count
        self.backend.close() # Should not raise error and not call mock_conn.close() again
        self.mock_conn.close.assert_not_called()
        self.assertIsNone(self.backend.conn)

    def test_insert_usage_success(self):
        self.backend._create_tables = MagicMock()
        self.backend.initialize() # To set up self.backend.conn

        sample_entry = UsageEntry(
            model="gpt-4",
            prompt_tokens=100,
            completion_tokens=200,
            total_tokens=300,
            cost=0.05,
            timestamp=datetime(2023, 1, 1, 12, 0, 0),
            caller_name="" # Added default caller_name
        )
        
        self.backend.insert_usage(sample_entry)

        self.mock_cursor.execute.assert_called_once()
        args, _ = self.mock_cursor.execute.call_args
        self.assertIn("INSERT INTO accounting_entries", args[0])
        # Check if all expected values from sample_entry are in args[1]
        self.assertIn(sample_entry.model, args[1])
        self.assertIn(sample_entry.prompt_tokens, args[1])
        self.assertIn(sample_entry.cost, args[1])
        
        self.mock_conn.commit.assert_called_once()

    def test_insert_usage_db_error(self):
        self.backend._create_tables = MagicMock()
        self.backend.initialize()
        self.mock_cursor.execute.side_effect = psycopg2.Error("Insert failed")

        sample_entry = UsageEntry(model="gpt-3.5-turbo", cost=0.01, caller_name="") # Minimal entry

        with self.assertRaises(psycopg2.Error): # Expecting the original psycopg2.Error
            self.backend.insert_usage(sample_entry)
        
        self.mock_conn.rollback.assert_called_once()
        self.mock_conn.commit.assert_not_called() # Ensure commit was not called on error

    def test_get_period_stats_success(self):
        self.backend._create_tables = MagicMock()
        self.backend.initialize()

        sample_db_row_dict = {
            'sum_prompt_tokens': 100, 'avg_prompt_tokens': 50.0,
            'sum_completion_tokens': 200, 'avg_completion_tokens': 100.0,
            'sum_total_tokens': 300, 'avg_total_tokens': 150.0,
            'sum_local_prompt_tokens': 0, 'avg_local_prompt_tokens': 0.0,
            'sum_local_completion_tokens': 0, 'avg_local_completion_tokens': 0.0,
            'sum_local_total_tokens': 0, 'avg_local_total_tokens': 0.0,
            'sum_cost': 0.05, 'avg_cost': 0.025,
            'sum_execution_time': 10.0, 'avg_execution_time': 5.0
        }
        self.mock_cursor.fetchone.return_value = sample_db_row_dict
        
        # Ensure the cursor is treated as RealDictCursor by mocking the cursor_factory if needed
        # If NeonBackend explicitly passes cursor_factory=RealDictCursor, this mock is more robust
        self.mock_conn.cursor.return_value = self.mock_conn.cursor.return_value # keep current mock
        # self.mock_conn.cursor.return_value.__enter__.return_value = self.mock_cursor # re-assign after potential modification
        
        # If the code is `with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:`
        # then self.mock_psycopg2_module.extras.RealDictCursor needs to be available or the factory itself mocked.
        # For simplicity, we assume the cursor object `self.mock_cursor` behaves as needed (returns dicts).


        start_dt = datetime(2023, 1, 1)
        end_dt = datetime(2023, 1, 31)
        stats = self.backend.get_period_stats(start_dt, end_dt)

        self.mock_cursor.execute.assert_called_once()
        args, _ = self.mock_cursor.execute.call_args
        self.assertIn("SELECT", args[0])
        self.assertIn("FROM accounting_entries", args[0])
        self.assertEqual(args[1], (start_dt, end_dt))
        
        self.assertIsInstance(stats, UsageStats)
        self.assertEqual(stats.sum_prompt_tokens, sample_db_row_dict['sum_prompt_tokens'])
        self.assertEqual(stats.avg_cost, sample_db_row_dict['avg_cost'])

    def test_get_period_stats_no_data(self):
        self.backend._create_tables = MagicMock()
        self.backend.initialize()

        # Simulate no rows returned or all aggregates are NULL (COALESCE handles this)
        # The NeonBackend's get_period_stats uses COALESCE, so fetchone will return a row of 0s/0.0s
        # if the query itself runs but finds no data matching the WHERE clause.
        # If fetchone() itself returns None (e.g. query error before aggregation, though unlikely for SELECT),
        # then the method should return a default UsageStats.
        # The current implementation has `if row:` so if fetchone is None, it creates UsageStats()
        # If fetchone returns a dict with None values, UsageStats(**row) would be called.
        # The COALESCE in SQL means the dict will have 0/0.0 not None.

        no_data_row = {
            'sum_prompt_tokens': 0, 'avg_prompt_tokens': 0.0,
            'sum_completion_tokens': 0, 'avg_completion_tokens': 0.0,
            'sum_total_tokens': 0, 'avg_total_tokens': 0.0,
            'sum_local_prompt_tokens': 0, 'avg_local_prompt_tokens': 0.0,
            'sum_local_completion_tokens': 0, 'avg_local_completion_tokens': 0.0,
            'sum_local_total_tokens': 0, 'avg_local_total_tokens': 0.0,
            'sum_cost': 0.0, 'avg_cost': 0.0,
            'sum_execution_time': 0.0, 'avg_execution_time': 0.0
        }
        self.mock_cursor.fetchone.return_value = no_data_row # Due to COALESCE

        start_dt = datetime(2023, 1, 1)
        end_dt = datetime(2023, 1, 31)
        stats = self.backend.get_period_stats(start_dt, end_dt)

        self.mock_cursor.execute.assert_called_once()
        self.assertIsInstance(stats, UsageStats)
        self.assertEqual(stats.sum_total_tokens, 0)
        self.assertEqual(stats.avg_cost, 0.0)
        # Check a few default values
        self.assertEqual(stats.sum_prompt_tokens, 0)

    def test_insert_api_request_success(self):
        self.backend._create_tables = MagicMock()
        self.backend.initialize()
        sample_request = APIRequest(
            model="text-davinci-003",
            username="test_user",
            input_tokens=50,
            output_tokens=150,
            cost=0.002,
            timestamp=datetime(2023, 2, 1, 10, 0, 0),
            caller_name=""
        )
        self.backend.insert_api_request(sample_request)
        self.mock_cursor.execute.assert_called_once()
        args, _ = self.mock_cursor.execute.call_args
        self.assertIn("INSERT INTO api_requests", args[0])
        self.assertIn(sample_request.model, args[1])
        self.assertIn(sample_request.username, args[1])
        self.mock_conn.commit.assert_called_once()

    def test_insert_api_request_db_error(self):
        self.backend._create_tables = MagicMock()
        self.backend.initialize()
        self.mock_cursor.execute.side_effect = psycopg2.Error("API Insert failed")
        sample_request = APIRequest(model="text-davinci-003", username="", caller_name="", input_tokens=0, output_tokens=0, cost=0.002)
        with self.assertRaises(psycopg2.Error):
            self.backend.insert_api_request(sample_request)
        self.mock_conn.rollback.assert_called_once()
        self.mock_conn.commit.assert_not_called()

    def test_insert_usage_limit_success(self):
        self.backend._create_tables = MagicMock()
        self.backend.initialize()
        sample_limit = UsageLimit(
            scope=LimitScope.USER.value,
            limit_type=LimitType.COST.value,
            max_value=100.0,
            interval_unit=TimeInterval.MONTH.value,
            interval_value=1,
            username="limit_user",
            model="all_models"
        )
        self.backend.insert_usage_limit(sample_limit)
        self.mock_cursor.execute.assert_called_once()
        args, _ = self.mock_cursor.execute.call_args
        self.assertIn("INSERT INTO usage_limits", args[0])
        self.assertEqual(args[1][0], sample_limit.scope) # Scope
        self.assertEqual(args[1][1], sample_limit.limit_type) # Limit Type
        self.assertEqual(args[1][2], sample_limit.max_value) # Max Value
        self.assertEqual(args[1][5], sample_limit.model) # Model Name
        self.assertEqual(args[1][6], sample_limit.username) # Username
        self.mock_conn.commit.assert_called_once()

    def test_insert_usage_limit_db_error(self):
        self.backend._create_tables = MagicMock()
        self.backend.initialize()
        self.mock_cursor.execute.side_effect = psycopg2.Error("Limit Insert failed")
        sample_limit = UsageLimit(scope=LimitScope.GLOBAL.value, limit_type=LimitType.COST.value, max_value=500.0, interval_unit=TimeInterval.DAY.value, interval_value=1)
        with self.assertRaises(psycopg2.Error):
            self.backend.insert_usage_limit(sample_limit)
        self.mock_conn.rollback.assert_called_once()
        self.mock_conn.commit.assert_not_called()

    def test_get_model_stats_success(self):
        self.backend._create_tables = MagicMock()
        self.backend.initialize()
        sample_db_rows = [
            {'model_name': 'gpt-4', 'sum_prompt_tokens': 1000, 'avg_prompt_tokens': 100.0, 'sum_cost': 1.2, 'avg_cost': 0.12,
             'sum_completion_tokens': 200, 'avg_completion_tokens': 20.0, 'sum_total_tokens': 1200, 'avg_total_tokens': 120.0,
             'sum_local_prompt_tokens': 0, 'avg_local_prompt_tokens': 0.0, 'sum_local_completion_tokens': 0, 'avg_local_completion_tokens': 0.0,
             'sum_local_total_tokens': 0, 'avg_local_total_tokens': 0.0, 'sum_execution_time': 50.0, 'avg_execution_time': 5.0},
            {'model_name': 'gpt-3.5-turbo', 'sum_prompt_tokens': 500, 'avg_prompt_tokens': 50.0, 'sum_cost': 0.5, 'avg_cost': 0.05,
             'sum_completion_tokens': 100, 'avg_completion_tokens': 10.0, 'sum_total_tokens': 600, 'avg_total_tokens': 60.0,
             'sum_local_prompt_tokens': 0, 'avg_local_prompt_tokens': 0.0, 'sum_local_completion_tokens': 0, 'avg_local_completion_tokens': 0.0,
             'sum_local_total_tokens': 0, 'avg_local_total_tokens': 0.0, 'sum_execution_time': 20.0, 'avg_execution_time': 2.0}
        ]
        self.mock_cursor.fetchall.return_value = sample_db_rows # fetchall is used in the code if RealDictCursor is used and iterated upon
        # If the code directly iterates the cursor (e.g. `for row in cur:`), then mock_cursor itself should be an iterable
        self.mock_cursor.__iter__.return_value = iter(sample_db_rows)


        start_dt = datetime(2023, 1, 1)
        end_dt = datetime(2023, 1, 31)
        model_stats_list = self.backend.get_model_stats(start_dt, end_dt)

        self.mock_cursor.execute.assert_called_once()
        args, _ = self.mock_cursor.execute.call_args
        self.assertIn("model_name,", args[0]) # Check for model_name in select
        self.assertIn("GROUP BY model_name", args[0])
        self.assertEqual(args[1], (start_dt, end_dt))

        self.assertEqual(len(model_stats_list), 2)
        self.assertEqual(model_stats_list[0][0], 'gpt-4')
        self.assertIsInstance(model_stats_list[0][1], UsageStats)
        self.assertEqual(model_stats_list[0][1].sum_cost, 1.2)
        self.assertEqual(model_stats_list[1][0], 'gpt-3.5-turbo')
        self.assertEqual(model_stats_list[1][1].sum_prompt_tokens, 500)

    def test_get_model_stats_no_data(self):
        self.backend._create_tables = MagicMock()
        self.backend.initialize()
        self.mock_cursor.__iter__.return_value = iter([]) # Simulate no rows

        start_dt = datetime(2023, 1, 1)
        end_dt = datetime(2023, 1, 31)
        model_stats_list = self.backend.get_model_stats(start_dt, end_dt)

        self.mock_cursor.execute.assert_called_once()
        self.assertEqual(len(model_stats_list), 0)

    def test_get_model_stats_db_error(self):
        self.backend._create_tables = MagicMock()
        self.backend.initialize()
        self.mock_cursor.execute.side_effect = psycopg2.Error("Model Stats failed")
        start_dt = datetime(2023, 1, 1)
        end_dt = datetime(2023, 1, 31)
        with self.assertRaises(psycopg2.Error):
            self.backend.get_model_stats(start_dt, end_dt)

    def test_get_model_rankings_success(self):
        self.backend._create_tables = MagicMock()
        self.backend.initialize()
        # Simulate cursor returning different data for each metric query
        # Example for 'total_tokens'
        total_tokens_ranking = [('gpt-4', 5000), ('gpt-3.5-turbo', 3000)]
        # Example for 'cost'
        cost_ranking = [('gpt-4', 15.50), ('claude-2', 12.30)]
        # ... and so on for other metrics in NeonBackend.get_model_rankings

        # We need to mock fetchall for each call to execute
        # The order of metrics in the NeonBackend.get_model_rankings matters here.
        # metrics = {"total_tokens": ..., "cost": ..., "prompt_tokens": ..., "completion_tokens": ..., "execution_time": ...}
        self.mock_cursor.fetchall.side_effect = [
            total_tokens_ranking, # For total_tokens query
            cost_ranking,         # For cost query
            [],                   # For prompt_tokens query (example)
            [],                   # For completion_tokens query
            []                    # For execution_time query
        ]

        start_dt = datetime(2023, 1, 1)
        end_dt = datetime(2023, 1, 31)
        rankings = self.backend.get_model_rankings(start_dt, end_dt)

        self.assertEqual(self.mock_cursor.execute.call_count, 5) # 5 metrics
        args, _ = self.mock_cursor.execute.call_args_list[0] # First call
        self.assertIn("SUM(total_tokens) AS aggregated_value", args[0])
        self.assertEqual(args[1], (start_dt, end_dt))

        args, _ = self.mock_cursor.execute.call_args_list[1] # Second call
        self.assertIn("SUM(cost) AS aggregated_value", args[0])

        self.assertEqual(rankings['total_tokens'], total_tokens_ranking)
        self.assertEqual(rankings['cost'], cost_ranking)
        self.assertEqual(rankings['prompt_tokens'], [])

    def test_get_model_rankings_no_data(self):
        self.backend._create_tables = MagicMock()
        self.backend.initialize()
        self.mock_cursor.fetchall.return_value = [] # No data for any metric

        start_dt = datetime(2023, 1, 1)
        end_dt = datetime(2023, 1, 31)
        rankings = self.backend.get_model_rankings(start_dt, end_dt)

        self.assertEqual(self.mock_cursor.execute.call_count, 5)
        for metric in rankings:
            self.assertEqual(rankings[metric], [])

    def test_get_model_rankings_db_error(self):
        self.backend._create_tables = MagicMock()
        self.backend.initialize()
        self.mock_cursor.execute.side_effect = psycopg2.Error("Rankings failed")
        start_dt = datetime(2023, 1, 1)
        end_dt = datetime(2023, 1, 31)
        with self.assertRaises(psycopg2.Error):
            self.backend.get_model_rankings(start_dt, end_dt)

    def test_tail_success(self):
        self.backend._create_tables = MagicMock()
        self.backend.initialize()
        sample_rows = [
            {'model_name': 'gpt-4', 'prompt_tokens': 10, 'cost': 0.1, 'timestamp': datetime(2023,3,1,10,0,5)},
            {'model_name': 'claude-2', 'prompt_tokens': 20, 'cost': 0.2, 'timestamp': datetime(2023,3,1,10,0,0)}
        ]
        self.mock_cursor.__iter__.return_value = iter(sample_rows)

        entries = self.backend.tail(n=2)

        self.mock_cursor.execute.assert_called_once()
        args, _ = self.mock_cursor.execute.call_args
        self.assertIn("SELECT * FROM accounting_entries", args[0])
        self.assertIn("ORDER BY timestamp DESC, id DESC", args[0])
        self.assertEqual(args[1], (2,)) # n=2

        self.assertEqual(len(entries), 2)
        self.assertIsInstance(entries[0], UsageEntry)
        self.assertEqual(entries[0].model, 'gpt-4')
        self.assertEqual(entries[1].cost, 0.2)

    def test_tail_no_data(self):
        self.backend._create_tables = MagicMock()
        self.backend.initialize()
        self.mock_cursor.__iter__.return_value = iter([])
        entries = self.backend.tail(n=5)
        self.mock_cursor.execute.assert_called_once()
        self.assertEqual(len(entries), 0)

    def test_tail_db_error(self):
        self.backend._create_tables = MagicMock()
        self.backend.initialize()
        self.mock_cursor.execute.side_effect = psycopg2.Error("Tail failed")
        with self.assertRaises(psycopg2.Error):
            self.backend.tail(n=3)

    def test_purge_success(self):
        self.backend._create_tables = MagicMock()
        self.backend.initialize()
        self.backend.purge()

        expected_calls = [
            call("DELETE FROM accounting_entries;"),
            call("DELETE FROM api_requests;"),
            call("DELETE FROM usage_limits;")
        ]
        self.mock_cursor.execute.assert_has_calls(expected_calls, any_order=False) # Order matters for DELETEs usually not, but check
        self.assertEqual(self.mock_cursor.execute.call_count, 3)
        self.mock_conn.commit.assert_called_once()

    def test_purge_db_error(self):
        self.backend._create_tables = MagicMock()
        self.backend.initialize()
        self.mock_cursor.execute.side_effect = psycopg2.Error("Purge failed")
        with self.assertRaises(psycopg2.Error):
            self.backend.purge()
        self.mock_conn.rollback.assert_called_once()
        self.mock_conn.commit.assert_not_called()

    def test_get_usage_limits_success_with_filters(self):
        self.backend._create_tables = MagicMock()
        self.backend.initialize()
        sample_limit_row = {
            'id': 1, 'scope': 'USER', 'limit_type': 'cost', 'max_value': 100.0,
            'interval_unit': 'monthly', 'interval_value': 1, 'model_name': 'gpt-4',
            'username': 'test_user', 'caller_name': 'test_caller',
            'created_at': datetime(2023,1,1), 'updated_at': datetime(2023,1,1)
        }
        self.mock_cursor.__iter__.return_value = iter([sample_limit_row])

        limits = self.backend.get_usage_limits(
            scope=LimitScope.USER,
            model='gpt-4',
            username='test_user',
            caller_name='test_caller'
        )

        self.mock_cursor.execute.assert_called_once()
        args, params = self.mock_cursor.execute.call_args[0] # call_args is a tuple (args, kwargs)
        
        self.assertIn("SELECT * FROM usage_limits WHERE", args)
        self.assertIn("scope = %s", args)
        self.assertIn("model_name = %s", args)
        self.assertIn("username = %s", args)
        self.assertIn("caller_name = %s", args)
        self.assertEqual(params, (LimitScope.USER.value, 'gpt-4', 'test_user', 'test_caller'))

        self.assertEqual(len(limits), 1)
        self.assertIsInstance(limits[0], UsageLimit)
        self.assertEqual(limits[0].scope, LimitScope.USER.value)
        self.assertEqual(limits[0].model, 'gpt-4') # Check model_name mapping
        self.assertEqual(limits[0].username, 'test_user')

    def test_get_usage_limits_success_no_filters(self):
        self.backend._create_tables = MagicMock()
        self.backend.initialize()
        self.mock_cursor.__iter__.return_value = iter([])
        self.backend.get_usage_limits()
        self.mock_cursor.execute.assert_called_once_with("SELECT * FROM usage_limits ORDER BY created_at DESC;", tuple())

    def test_get_usage_limits_no_data(self):
        self.backend._create_tables = MagicMock()
        self.backend.initialize()
        self.mock_cursor.__iter__.return_value = iter([])
        limits = self.backend.get_usage_limits(scope=LimitScope.USER)
        self.assertEqual(len(limits), 0)

    def test_get_usage_limits_enum_conversion_error(self):
        self.backend._create_tables = MagicMock()
        self.backend.initialize()
        invalid_enum_row = {
            'id': 1, 'scope': 'INVALID_SCOPE', 'limit_type': 'COST', 'max_value': 100.0,
            'interval_unit': 'MONTHLY', 'interval_value': 1,
            'created_at': datetime(2023,1,1), 'updated_at': datetime(2023,1,1)
        }
        self.mock_cursor.__iter__.return_value = iter([invalid_enum_row])
        with self.assertRaises(ValueError): # psycopg2.Error or ValueError depending on where it's caught
            self.backend.get_usage_limits()


    def test_get_usage_limits_db_error(self):
        self.backend._create_tables = MagicMock()
        self.backend.initialize()
        self.mock_cursor.execute.side_effect = psycopg2.Error("Get limits failed")
        with self.assertRaises(psycopg2.Error):
            self.backend.get_usage_limits()

    def test_get_api_requests_for_quota_success(self):
        self.backend._create_tables = MagicMock()
        self.backend.initialize()
        start_time = datetime(2023, 1, 1, 0, 0, 0)

        # Test for COST
        self.mock_cursor.fetchone.return_value = (123.45,)
        cost_val = self.backend.get_api_requests_for_quota(start_time, LimitType.COST, model='gpt-4')
        self.mock_cursor.execute.assert_called_with(
            "SELECT COALESCE(SUM(cost), 0.0) AS aggregated_value FROM api_requests WHERE timestamp >= %s AND model_name = %s;",
            (start_time, 'gpt-4')
        )
        self.assertEqual(cost_val, 123.45)

        # Test for REQUESTS
        self.mock_cursor.fetchone.return_value = (50,)
        requests_val = self.backend.get_api_requests_for_quota(start_time, LimitType.REQUESTS, username='user1')
        self.mock_cursor.execute.assert_called_with(
            "SELECT COUNT(*) AS aggregated_value FROM api_requests WHERE timestamp >= %s AND username = %s;",
            (start_time, 'user1')
        )
        self.assertEqual(requests_val, 50)
        
        # Test for INPUT_TOKENS
        self.mock_cursor.fetchone.return_value = (10000,)
        input_tokens_val = self.backend.get_api_requests_for_quota(start_time, LimitType.INPUT_TOKENS, caller_name='caller_A')
        self.mock_cursor.execute.assert_called_with(
            "SELECT COALESCE(SUM(input_tokens), 0) AS aggregated_value FROM api_requests WHERE timestamp >= %s AND caller_name = %s;",
            (start_time, 'caller_A')
        )
        self.assertEqual(input_tokens_val, 10000)

    def test_get_api_requests_for_quota_no_data(self):
        self.backend._create_tables = MagicMock()
        self.backend.initialize()
        self.mock_cursor.fetchone.return_value = (0.0,) # COALESCE should return 0 or 0.0
        val = self.backend.get_api_requests_for_quota(datetime.now(), LimitType.COST)
        self.assertEqual(val, 0.0)
        
        self.mock_cursor.fetchone.return_value = (0,) # For COUNT or SUM(tokens)
        val_tokens = self.backend.get_api_requests_for_quota(datetime.now(), LimitType.INPUT_TOKENS)
        self.assertEqual(val_tokens, 0)


    def test_get_api_requests_for_quota_db_error(self):
        self.backend._create_tables = MagicMock()
        self.backend.initialize()
        self.mock_cursor.execute.side_effect = psycopg2.Error("Quota check failed")
        with self.assertRaises(psycopg2.Error):
            self.backend.get_api_requests_for_quota(datetime.now(), LimitType.COST)

    def test_get_api_requests_for_quota_invalid_type(self):
        self.backend._create_tables = MagicMock()
        self.backend.initialize()
        with self.assertRaisesRegex(ValueError, "is not a valid LimitType"):
            self.backend.get_api_requests_for_quota(datetime.now(), LimitType("unsupported"))


    def test_execute_query_success(self):
        self.backend._create_tables = MagicMock()
        self.backend.initialize()
        sample_query = "SELECT * FROM accounting_entries WHERE cost > %s;" # Example with params, though execute_query doesn't take params directly
        # The current execute_query doesn't support parameterized queries directly, it expects a full query string.
        # If parameters are needed, they should be part of the `query` string already (careful with SQLi if not handled properly).
        # For this test, we assume `query` is a complete SQL string.
        
        raw_query_for_execute = "SELECT * FROM accounting_entries WHERE cost > 10;"
        expected_result = [{'id': 1, 'cost': 20.0}, {'id': 2, 'cost': 30.0}]
        self.mock_cursor.fetchall.return_value = expected_result # fetchall for RealDictCursor
        
        # If RealDictCursor is used, the iteration over cursor also works (for row in cur)
        # self.mock_cursor.__iter__.return_value = iter(expected_result)


        result = self.backend.execute_query(raw_query_for_execute)

        self.mock_cursor.execute.assert_called_once_with(raw_query_for_execute)
        self.assertEqual(result, expected_result)

    def test_execute_query_non_select_error(self):
        self.backend._create_tables = MagicMock()
        self.backend.initialize()
        non_select_query = "DELETE FROM accounting_entries;"
        with self.assertRaisesRegex(ValueError, "Only SELECT queries are allowed"):
            self.backend.execute_query(non_select_query)
        self.mock_cursor.execute.assert_not_called()

    def test_execute_query_db_error(self):
        self.backend._create_tables = MagicMock()
        self.backend.initialize()
        self.mock_cursor.execute.side_effect = psycopg2.Error("Custom query failed")
        with self.assertRaises(psycopg2.Error):
            self.backend.execute_query("SELECT 1;")

    # --- Tests for remaining BaseBackend methods ---

    def test_get_usage_costs_success(self):
        self.backend._create_tables = MagicMock()
        self.backend.initialize()
        self.mock_cursor.fetchone.return_value = (123.45,) # Sum of costs

        start_dt = datetime(2023,1,1)
        end_dt = datetime(2023,1,31)
        costs = self.backend.get_usage_costs("user123", start_date=start_dt, end_date=end_dt)

        self.mock_cursor.execute.assert_called_once()
        args, params = self.mock_cursor.execute.call_args[0]
        self.assertIn("SELECT COALESCE(SUM(cost), 0.0) FROM accounting_entries WHERE username = %s", args)
        self.assertIn("AND timestamp >= %s", args)
        self.assertIn("AND timestamp <= %s", args)
        self.assertEqual(params, ("user123", start_dt, end_dt))
        self.assertEqual(costs, 123.45)

    def test_get_usage_costs_no_data(self):
        self.backend._create_tables = MagicMock()
        self.backend.initialize()
        self.mock_cursor.fetchone.return_value = (0.0,) # COALESCE returns 0.0
        costs = self.backend.get_usage_costs("user_unknown")
        self.assertEqual(costs, 0.0)

    def test_get_usage_costs_db_error(self):
        self.backend._create_tables = MagicMock()
        self.backend.initialize()
        self.mock_cursor.execute.side_effect = psycopg2.Error("get_usage_costs failed")
        with self.assertRaises(psycopg2.Error):
            self.backend.get_usage_costs("user123")

    def test_set_usage_limit_base_method_success(self):
        self.backend._create_tables = MagicMock()
        self.backend.initialize()
        # This method calls insert_usage_limit internally, so we check those calls
        # Reset mocks for insert_usage_limit if it was called during initialize's _create_tables or similar
        # Or mock insert_usage_limit itself on the instance
        self.backend.insert_usage_limit = MagicMock(name="insert_usage_limit_mock")

        user_id = "test_user_for_set_limit"
        limit_amount = 200.0
        limit_type_str = "cost"
        
        self.backend.set_usage_limit(user_id, limit_amount, limit_type_str)

        self.backend.insert_usage_limit.assert_called_once()
        called_arg = self.backend.insert_usage_limit.call_args[0][0]
        self.assertIsInstance(called_arg, UsageLimit)
        self.assertEqual(called_arg.username, user_id)
        self.assertEqual(called_arg.max_value, limit_amount)
        self.assertEqual(called_arg.limit_type, LimitType.COST.value)
        self.assertEqual(called_arg.scope, LimitScope.USER.value) # Default from method
        self.assertEqual(called_arg.interval_unit, TimeInterval.MONTH.value) # Default

    def test_set_usage_limit_base_method_invalid_type_str(self):
        self.backend._create_tables = MagicMock()
        self.backend.initialize()
        with self.assertRaisesRegex(ValueError, "Invalid limit_type string"):
            self.backend.set_usage_limit("user1", 100.0, "invalid_type_string")

    def test_set_usage_limit_base_method_db_error(self):
        self.backend._create_tables = MagicMock()
        self.backend.initialize()
        self.backend.insert_usage_limit = MagicMock(side_effect=psycopg2.Error("Insert from set_usage_limit failed"))
        
        with self.assertRaises(psycopg2.Error):
            self.backend.set_usage_limit("user_err", 100.0, "cost")


    def test_get_usage_limit_base_method_success(self):
        self.backend._create_tables = MagicMock()
        self.backend.initialize()
        # This method calls self.get_usage_limits internally
        expected_limits = [
            UsageLimit(scope=LimitScope.USER.value, limit_type=LimitType.COST.value, max_value=100.0, interval_unit=TimeInterval.MONTH.value, interval_value=1, username="user_abc")
        ]
        self.backend.get_usage_limits = MagicMock(return_value=expected_limits)

        retrieved_limits = self.backend.get_usage_limit("user_abc")

        self.backend.get_usage_limits.assert_called_once_with(username="user_abc")
        self.assertEqual(retrieved_limits, expected_limits)

    def test_get_usage_limit_base_method_no_data(self):
        self.backend._create_tables = MagicMock()
        self.backend.initialize()
        self.backend.get_usage_limits = MagicMock(return_value=[])
        retrieved_limits = self.backend.get_usage_limit("user_xyz")
        self.assertEqual(retrieved_limits, [])


    def test_record_api_request_base_method_success(self):
        self.backend._create_tables = MagicMock()
        self.backend.initialize()
        # This method calls self.insert_api_request
        self.backend.insert_api_request = MagicMock(name="insert_api_request_mock")
        
        request_data = {
            "model": "gpt-4-turbo",
            "username": "test_user_record",
            "input_tokens": 10,
            "output_tokens": 20,
            "cost": 0.001
        }
        self.backend.record_api_request(request_data)

        self.backend.insert_api_request.assert_called_once()
        called_arg = self.backend.insert_api_request.call_args[0][0]
        self.assertIsInstance(called_arg, APIRequest)
        self.assertEqual(called_arg.model, request_data["model"])
        self.assertEqual(called_arg.username, request_data["username"])
        self.assertEqual(called_arg.cost, request_data["cost"])

    def test_record_api_request_base_method_missing_key(self):
        self.backend._create_tables = MagicMock()
        self.backend.initialize()
        request_data_missing = {"username": "some_user"} # Missing model
        with self.assertRaisesRegex(ValueError, "model .* is required"):
            self.backend.record_api_request(request_data_missing)


if __name__ == '__main__':
    unittest.main()
