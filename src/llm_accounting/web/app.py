from flask import Flask, render_template, request, current_app, redirect, url_for
from datetime import datetime
import math
import json # For Plotly charts
import plotly
import plotly.express as px
import pandas as pd # For easier data manipulation for charts

app = Flask(__name__)

# Configuration for the Flask app
# These can be overridden by the main application
# APP_HOST, APP_PORT, APP_ENABLED are set by the caller of run_server

@app.before_request
def ensure_instance():
    if not hasattr(current_app, 'llm_accounting_instance') and request.endpoint not in ['static']:
        # This could redirect to an error page or abort
        # For now, it implies the app wasn't started correctly via LLMAccounting.initialize_web_ui
        print("Error: llm_accounting_instance not found on current_app.")
        # Consider abort(500, "LLMAccounting instance not available")
        # Or, if running directly for dev, create a mock/default one (not for production)
        pass


@app.route('/')
def home():
    # Simple home page, maybe linking to other pages or showing basic info
    return render_template('base.html') # Or a dedicated home.html if created

def _parse_date(date_str):
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        return None # Or raise a custom error to show in UI

def run_server(llm_instance, host="127.0.0.1", port=5000, enabled=False):
    """
    Runs the Flask development server.
    Allows overriding host and port.
    """
    if enabled:
        app.llm_accounting_instance = llm_instance # Store the instance on the app object
        app.run(host=host, port=port)

# --- Accounting Entries View ---
@app.route('/accounting')
def accounting_entries_view():
    if not hasattr(current_app, 'llm_accounting_instance') or not current_app.llm_accounting_instance:
        return "Error: LLM Accounting instance not available.", 500

    backend = current_app.llm_accounting_instance.backend
    
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 20, type=int)
    sort_by = request.args.get('sort_by', 'timestamp')
    sort_order = request.args.get('sort_order', 'desc')

    filters = {}
    if request.args.get('project'): filters['project'] = request.args.get('project')
    if request.args.get('model'): filters['model'] = request.args.get('model')
    if request.args.get('caller_name'): filters['caller_name'] = request.args.get('caller_name')
    if request.args.get('username'): filters['username'] = request.args.get('username')
    if request.args.get('search_term'): filters['search_term'] = request.args.get('search_term')
    
    timestamp_start_str = request.args.get('timestamp_start')
    timestamp_end_str = request.args.get('timestamp_end')
    
    timestamp_start = _parse_date(timestamp_start_str)
    timestamp_end = _parse_date(timestamp_end_str)
    if timestamp_start: filters['timestamp_start'] = timestamp_start
    if timestamp_end: filters['timestamp_end'] = timestamp_end

    try:
        entries, total_entries = backend.get_accounting_entries(
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            filters=filters
        )
    except Exception as e:
        # Log the error e
        return f"Error fetching accounting entries: {e}", 500

    total_pages = math.ceil(total_entries / page_size) if page_size > 0 else 0
    
    return render_template(
        'accounting_entries.html',
        entries=entries,
        current_page=page,
        total_pages=total_pages,
        page_size=page_size,
        total_entries=total_entries,
        sort_by=sort_by,
        sort_order=sort_order,
        filters=request.args # Pass all current args to easily reconstruct filter form and links
    )

# --- Usage Limits View ---
@app.route('/limits')
def usage_limits_view():
    if not hasattr(current_app, 'llm_accounting_instance') or not current_app.llm_accounting_instance:
        return "Error: LLM Accounting instance not available.", 500
    backend = current_app.llm_accounting_instance.backend

    filters = {}
    if request.args.get('project_name'): filters['project_name'] = request.args.get('project_name')
    if request.args.get('model'): filters['model'] = request.args.get('model')
    if request.args.get('username'): filters['username'] = request.args.get('username')
    if request.args.get('caller_name'): filters['caller_name'] = request.args.get('caller_name')
    if request.args.get('scope'): filters['scope'] = request.args.get('scope')

    try:
        limits = backend.get_usage_limits_ui(filters=filters)
    except Exception as e:
        # Log the error e
        return f"Error fetching usage limits: {e}", 500

    return render_template(
        'usage_limits.html',
        limits=limits,
        filters=request.args
    )

# --- Audit Log Entries View ---
@app.route('/audit')
def audit_log_entries_view():
    if not hasattr(current_app, 'llm_accounting_instance') or not current_app.llm_accounting_instance:
        return "Error: LLM Accounting instance not available.", 500
    backend = current_app.llm_accounting_instance.backend

    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 20, type=int)
    sort_by = request.args.get('sort_by', 'timestamp')
    sort_order = request.args.get('sort_order', 'desc')

    filters = {}
    if request.args.get('project'): filters['project'] = request.args.get('project')
    if request.args.get('model'): filters['model'] = request.args.get('model')
    # Note: AuditLogEntryModel uses 'user_name' and 'app_name'
    if request.args.get('user_name'): filters['user_name'] = request.args.get('user_name')
    if request.args.get('app_name'): filters['app_name'] = request.args.get('app_name')
    if request.args.get('log_type'): filters['log_type'] = request.args.get('log_type')
    if request.args.get('search_term'): filters['search_term'] = request.args.get('search_term')

    timestamp_start_str = request.args.get('timestamp_start')
    timestamp_end_str = request.args.get('timestamp_end')
    
    timestamp_start = _parse_date(timestamp_start_str)
    timestamp_end = _parse_date(timestamp_end_str)
    if timestamp_start: filters['timestamp_start'] = timestamp_start
    if timestamp_end: filters['timestamp_end'] = timestamp_end
    
    try:
        entries, total_entries = backend.get_audit_log_entries(
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            filters=filters
        )
    except Exception as e:
        # Log the error e
        return f"Error fetching audit log entries: {e}", 500

    total_pages = math.ceil(total_entries / page_size) if page_size > 0 else 0

    return render_template(
        'audit_log_entries.html',
        entries=entries,
        current_page=page,
        total_pages=total_pages,
        page_size=page_size,
        total_entries=total_entries,
        sort_by=sort_by,
        sort_order=sort_order,
        filters=request.args
    )


if __name__ == '__main__':
    # This part is for direct execution (testing/dev)
    # It won't have a real LLMAccounting instance unless we mock or create one.
    # For robust direct running, you'd initialize a MockBackend or a temporary SQLite backend here.
    print("Running Flask app directly. LLMAccounting instance will be missing unless mocked.")
    
    # Example: Using a MockBackend if run directly
    from llm_accounting import LLMAccounting
    from llm_accounting.backends import MockBackend
    mock_llm_instance = LLMAccounting(backend=MockBackend())
    mock_llm_instance.initialize() # Initialize the backend
    
    # Populate with some mock data for testing UI
    from llm_accounting.backends.base import UsageEntry as MockUsageEntry, AuditLogEntry as MockAuditLogEntry
    from llm_accounting.models.limits import UsageLimitDTO as MockLimitDTO, LimitScope, LimitType, TimeInterval

    mock_backend = mock_llm_instance.backend
    if isinstance(mock_backend, MockBackend): # Check if it's actually MockBackend
        for i in range(50):
            mock_backend.insert_usage(MockUsageEntry(model=f'model_{i%5}', project=f'project_{i%2}', username=f'user_{i%10}', caller_name=f'app_{i%3}', prompt_tokens=100+i*10, completion_tokens=50+i*5, cost=0.01+i*0.001, timestamp=datetime.now()))
            mock_backend.log_audit_event(MockAuditLogEntry(app_name=f'app_{i%3}', user_name=f'user_{i%10}', model=f'model_{i%5}', project=f'project_{i%2}', log_type='event', prompt_text=f'prompt {i}', response_text=f'response {i}', timestamp=datetime.now()))
        mock_backend.insert_usage_limit(MockLimitDTO(scope=LimitScope.GLOBAL, limit_type=LimitType.COST, max_value=100.0, interval_unit=TimeInterval.MONTHLY, interval_value=1))

    run_server(llm_instance=mock_llm_instance, host="127.0.0.1", port=5005, enabled=True)


# --- Statistics View ---
AVAILABLE_GROUP_BY_DIMENSIONS = ['project', 'model', 'username', 'caller_name', 'time_group'] # time_group is special
AVAILABLE_AGGREGATES = [
    'sum_prompt_tokens', 'sum_completion_tokens', 'sum_total_tokens', 'sum_cost', 
    'sum_execution_time', 'avg_prompt_tokens', 'avg_completion_tokens', 
    'avg_total_tokens', 'avg_cost', 'avg_execution_time', 'count_entries'
]

@app.route('/statistics')
def statistics_view():
    if not hasattr(current_app, 'llm_accounting_instance') or not current_app.llm_accounting_instance:
        return "Error: LLM Accounting instance not available.", 500
    backend = current_app.llm_accounting_instance.backend

    # Get parameters from request
    selected_group_by = request.args.getlist('group_by')
    selected_aggregates = request.args.getlist('aggregates')
    time_horizon = request.args.get('time_horizon', 'all_time') # Default to 'all_time'
    
    timestamp_start_str = request.args.get('timestamp_start')
    timestamp_end_str = request.args.get('timestamp_end')
    timestamp_start = _parse_date(timestamp_start_str)
    timestamp_end = _parse_date(timestamp_end_str)

    additional_filters = {}
    if request.args.get('filter_project'): additional_filters['project'] = request.args.get('filter_project')
    if request.args.get('filter_model'): additional_filters['model'] = request.args.get('filter_model')
    if request.args.get('filter_username'): additional_filters['username'] = request.args.get('filter_username')
    if request.args.get('filter_caller_name'): additional_filters['caller_name'] = request.args.get('filter_caller_name')

    statistics_data = []
    chart_json = None

    # Only fetch data if there are selections for group_by and aggregates
    if selected_group_by and selected_aggregates:
        time_filters_for_backend = {}
        if time_horizon == 'custom' and timestamp_start:
            time_filters_for_backend['timestamp_start'] = timestamp_start
        if time_horizon == 'custom' and timestamp_end:
            time_filters_for_backend['timestamp_end'] = timestamp_end
        
        # Adjust time_horizon for backend if 'all_time' was selected
        actual_time_horizon_for_backend = time_horizon
        if time_horizon == 'all_time':
             # Backend's get_custom_stats might expect 'daily', 'weekly', 'monthly', or 'custom'.
             # If 'all_time' means no time grouping, then time_horizon for backend should reflect that.
             # This depends on backend implementation. For now, let's assume 'custom' with no time_filters
             # means all time, or backend handles 'all_time' or empty time_horizon.
             # The current backend implementation for get_custom_stats does not explicitly handle 'all_time' for date_trunc.
             # It groups by time if time_horizon is daily/weekly/monthly.
             # If no time_horizon is needed for grouping, pass empty or handle in backend.
             # For simplicity, if 'all_time', we won't pass a time_horizon that forces time grouping.
             # Let's assume 'custom' with no time_filters implies all time if no specific time_group is in selected_group_by
            if 'time_group' not in selected_group_by:
                 actual_time_horizon_for_backend = 'custom' # Effectively no time-based grouping by backend
            else: # if 'time_group' is explicitly requested with 'all_time', it's ambiguous. Default to daily for now.
                 actual_time_horizon_for_backend = 'daily'


        try:
            statistics_data = backend.get_custom_stats(
                group_by=[gb for gb in selected_group_by if gb != 'time_group'], # time_group is handled by time_horizon
                aggregates=selected_aggregates,
                time_horizon=actual_time_horizon_for_backend if 'time_group' in selected_group_by or time_horizon not in ['all_time', 'custom'] else 'custom', # only pass daily/weekly/monthly if time_group is relevant
                time_filters=time_filters_for_backend,
                additional_filters=additional_filters
            )
        except Exception as e:
            return f"Error fetching statistics data: {str(e)}", 500

        if statistics_data:
            try:
                # Create a Plotly figure
                df = pd.DataFrame(statistics_data)
                fig = None
                
                # Determine chart type based on selections
                # This is a simplified example. More sophisticated logic would be needed for robust chart generation.
                if df.empty:
                    chart_json = None
                elif 'time_group' in df.columns and len(selected_group_by) <= 2 and len(selected_aggregates) == 1:
                    # Line chart for time series data
                    group_col = [col for col in selected_group_by if col != 'time_group']
                    color_col = group_col[0] if group_col else None
                    y_col = selected_aggregates[0]
                    
                    if y_col not in df.columns: # Should not happen if backend works
                        chart_json = None
                    else:
                        df = df.sort_values(by=['time_group'] + ([color_col] if color_col else []))
                        fig = px.line(df, x='time_group', y=y_col, color=color_col, title="Time Series Analysis")
                
                elif len(selected_group_by) == 1 and len(selected_aggregates) == 1:
                    # Bar chart for single dimension, single aggregate
                    x_col = selected_group_by[0]
                    y_col = selected_aggregates[0]
                    if x_col in df.columns and y_col in df.columns:
                         df = df.sort_values(by=y_col, ascending=False) # Sort for better viz
                         fig = px.bar(df.head(20), x=x_col, y=y_col, title=f"{y_col} by {x_col}") # Top 20
                
                # Fallback or more complex chart logic here...
                # else:
                    # Could do parallel categories, sunburst, treemap for multi-dimensional data
                    # Or simply don't generate a chart if too complex for simple examples.

                if fig:
                    chart_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

            except Exception as e:
                # Log chart generation error: e
                print(f"Error generating chart: {e}") # For debugging
                chart_json = None # Ensure it's None if error occurs

    # Prepare parameters to pass back to template for form repopulation
    selected_params_for_template = {
        'group_by': selected_group_by,
        'aggregates': selected_aggregates,
        'time_horizon': time_horizon,
        'timestamp_start': timestamp_start_str if timestamp_start_str else '',
        'timestamp_end': timestamp_end_str if timestamp_end_str else '',
        'additional_filters': {
            'project': request.args.get('filter_project', ''),
            'model': request.args.get('filter_model', ''),
            'username': request.args.get('filter_username', ''),
            'caller_name': request.args.get('filter_caller_name', '')
        }
    }

    return render_template(
        'statistics.html',
        statistics_data=statistics_data,
        chart_json=chart_json,
        available_group_by_dimensions=AVAILABLE_GROUP_BY_DIMENSIONS,
        available_aggregates=AVAILABLE_AGGREGATES,
        selected_params=selected_params_for_template,
        # Pass other necessary params for form repopulation if any
    )
