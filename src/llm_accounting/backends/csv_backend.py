import os
import csv
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple 
from datetime import datetime, timezone # Added timezone
from typing_extensions import override 

from .base import BaseBackend, UsageEntry, UsageStats, AuditLogEntry
from ..models.limits import LimitScope, LimitType, UsageLimitDTO

logger = logging.getLogger(__name__)

class CSVBackend(BaseBackend):
    DEFAULT_DATA_DIR = "data/llm_accounting_csv" 
    ACCOUNTING_FILE_NAME = "accounting.csv"
    AUDIT_FILE_NAME = "audit.csv"
    LIMITS_FILE_NAME = "limits.csv"

    ACCOUNTING_FIELDNAMES = [
        "id", "model", "prompt_tokens", "completion_tokens", "total_tokens",
        "local_prompt_tokens", "local_completion_tokens", "local_total_tokens",
        "cost", "execution_time", "timestamp", "caller_name", "username", "project",
        "cached_tokens", "reasoning_tokens"
    ]
    AUDIT_FIELDNAMES = [
        "id", "timestamp", "app_name", "user_name", "model", "prompt_text",
        "response_text", "remote_completion_id", "project", "log_type"
    ]
    LIMITS_FIELDNAMES = [
        "id", "scope", "limit_type", "model", "username", "caller_name", "project_name",
        "max_value", "interval_unit", "interval_value", "created_at", "updated_at"
    ]

    def __init__(self, data_dir: Optional[str] = None, **kwargs):
        super().__init__() 
        
        if data_dir is None:
            self.data_dir = self.DEFAULT_DATA_DIR
        else:
            self.data_dir = data_dir
        
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)
        logger.info(f"CSVBackend data directory set to: {self.data_dir}")

        self.accounting_file = str(Path(self.data_dir) / self.ACCOUNTING_FILE_NAME)
        self.audit_file = str(Path(self.data_dir) / self.AUDIT_FILE_NAME)
        self.limits_file = str(Path(self.data_dir) / self.LIMITS_FILE_NAME)

        self._ensure_file_exists(self.accounting_file, self.ACCOUNTING_FIELDNAMES)
        self._ensure_file_exists(self.audit_file, self.AUDIT_FIELDNAMES)
        self._ensure_file_exists(self.limits_file, self.LIMITS_FIELDNAMES)

        self._mock_accounting_entries: List[UsageEntry] = []
        self._mock_audit_entries: List[AuditLogEntry] = []
        self._mock_limits_entries: List[UsageLimitDTO] = []
        self._next_id = 1 

    def _path_exists(self, file_path: str) -> bool:
        return Path(file_path).exists()

    def _ensure_file_exists(self, file_path: str, headers: List[str]):
        file_path_obj = Path(file_path)
        is_new_file = not file_path_obj.exists() or file_path_obj.stat().st_size == 0
        
        if is_new_file:
            try:
                with open(file_path_obj, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)
                logger.info(f"Created new CSV file with headers: {file_path}")
            except IOError as e:
                logger.error(f"Error creating file {file_path}: {e}")
                raise

    @override
    def initialize(self) -> None:
        logger.info("CSVBackend initialized. Files and directories checked/created in __init__.")
        pass

    @override
    def close(self) -> None:
        pass

    @override
    def _ensure_connected(self) -> None:
        pass

    @override
    def insert_usage(self, entry: UsageEntry) -> None:
        logger.debug(f"CSVBackend: insert_usage called with {entry}")
        # Ensure entry has default 0 for token fields if they are None for calculations
        entry.prompt_tokens = entry.prompt_tokens or 0
        entry.completion_tokens = entry.completion_tokens or 0
        entry.total_tokens = entry.total_tokens or (entry.prompt_tokens + entry.completion_tokens)
        entry.cost = entry.cost or 0.0
        entry.timestamp = entry.timestamp or datetime.now(timezone.utc)

        if entry.id is None: 
            entry.id = self._next_id
            self._next_id += 1
        self._mock_accounting_entries.append(entry)

    @override
    def get_period_stats(self, start: datetime, end: datetime) -> UsageStats:
        logger.debug(f"CSVBackend: get_period_stats called for {start}-{end}")
        
        filtered_entries = [
            e for e in self._mock_accounting_entries
            if e.timestamp and start <= e.timestamp < end
        ]

        if not filtered_entries:
            return UsageStats()

        sum_prompt_tokens = sum(e.prompt_tokens for e in filtered_entries if e.prompt_tokens is not None)
        sum_completion_tokens = sum(e.completion_tokens for e in filtered_entries if e.completion_tokens is not None)
        sum_total_tokens = sum(e.total_tokens for e in filtered_entries if e.total_tokens is not None)
        sum_cost = sum(e.cost for e in filtered_entries if e.cost is not None)
        # sum_execution_time and local tokens are not explicitly handled here yet
        
        num_requests = len(filtered_entries)

        return UsageStats(
            sum_prompt_tokens=sum_prompt_tokens,
            sum_completion_tokens=sum_completion_tokens,
            sum_total_tokens=sum_total_tokens,
            sum_cost=sum_cost,
            avg_prompt_tokens=sum_prompt_tokens / num_requests if num_requests > 0 else 0.0,
            avg_completion_tokens=sum_completion_tokens / num_requests if num_requests > 0 else 0.0,
            avg_total_tokens=sum_total_tokens / num_requests if num_requests > 0 else 0.0,
            avg_cost=sum_cost / num_requests if num_requests > 0 else 0.0
            # Other UsageStats fields will default to 0
        )

    @override
    def get_model_stats(self, start: datetime, end: datetime) -> List[Tuple[str, UsageStats]]:
        logger.debug(f"CSVBackend: get_model_stats called for {start}-{end}")
        # Placeholder, can be expanded if tests require it
        return []

    @override
    def get_model_rankings(self, start: datetime, end: datetime) -> Dict[str, List[Tuple[str, Any]]]:
        logger.debug(f"CSVBackend: get_model_rankings called for {start}-{end}")
        return {}

    @override
    def purge(self) -> None:
        logger.info("CSVBackend: purge called. Clearing mock data and re-initializing CSV files with headers.")
        self._mock_accounting_entries = []
        self._mock_audit_entries = []
        self._mock_limits_entries = []
        self._next_id = 1
        
        for file_path_str, headers in [
            (self.accounting_file, self.ACCOUNTING_FIELDNAMES),
            (self.audit_file, self.AUDIT_FIELDNAMES),
            (self.limits_file, self.LIMITS_FIELDNAMES),
        ]:
            try:
                # Overwrite file with only headers
                with open(file_path_str, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)
                logger.debug(f"Re-initialized (purged) file with headers: {file_path_str}")
            except IOError as e:
                logger.error(f"Error purging file {file_path_str}: {e}")

    @override
    def tail(self, n: int = 10, model: Optional[str] = None, username: Optional[str] = None, 
             caller_name: Optional[str] = None, project: Optional[str] = None) -> List[UsageEntry]:
        logger.debug(f"CSVBackend: tail({n}, model={model}, username={username}, caller_name={caller_name}, project={project}) called.")
        
        # Apply filters
        temp_entries = self._mock_accounting_entries
        if model:
            temp_entries = [e for e in temp_entries if e.model == model]
        if username:
            temp_entries = [e for e in temp_entries if e.username == username]
        if caller_name:
            temp_entries = [e for e in temp_entries if e.caller_name == caller_name]
        if project:
            temp_entries = [e for e in temp_entries if e.project == project]
            
        # Sort by timestamp (assuming UsageEntry.timestamp is datetime)
        # and then by ID for tie-breaking to get consistent "last N"
        # For mock, assuming append order is chronological enough for basic tail.
        # A more robust mock would sort by timestamp.
        # For now, just slicing the filtered list.
        return temp_entries[-n:]


    @override
    def execute_query(self, query: str) -> list[dict]:
        logger.debug(f"CSVBackend: execute_query called with '{query}' (not supported)")
        return [] 

    @override
    def get_usage_limits(
        self,
        scope: Optional[LimitScope] = None, model: Optional[str] = None,
        username: Optional[str] = None, caller_name: Optional[str] = None,
        project_name: Optional[str] = None, filter_project_null: Optional[bool] = None,
        filter_username_null: Optional[bool] = None, filter_caller_name_null: Optional[bool] = None,
    ) -> List[UsageLimitDTO]:
        logger.debug(f"CSVBackend: get_usage_limits called with filters: scope={scope}, model={model}, username={username}, caller_name={caller_name}, project_name={project_name}")
        
        results = self._mock_limits_entries
        if scope:
            results = [r for r in results if r.scope == scope]
        if model:
            results = [r for r in results if r.model == model]
        
        if username is not None:
            results = [r for r in results if r.username == username]
        elif filter_username_null is True:
            results = [r for r in results if r.username is None]
        elif filter_username_null is False: # Explicitly not null
            results = [r for r in results if r.username is not None]
            
        if caller_name is not None:
            results = [r for r in results if r.caller_name == caller_name]
        elif filter_caller_name_null is True:
            results = [r for r in results if r.caller_name is None]
        elif filter_caller_name_null is False:
            results = [r for r in results if r.caller_name is not None]

        if project_name is not None:
            results = [r for r in results if r.project_name == project_name]
        elif filter_project_null is True:
            results = [r for r in results if r.project_name is None]
        elif filter_project_null is False:
            results = [r for r in results if r.project_name is not None]
            
        return list(results) # Return a copy

    @override
    def get_accounting_entries_for_quota(
        self, start_time: datetime, limit_type: LimitType,
        model: Optional[str] = None, username: Optional[str] = None,
        caller_name: Optional[str] = None, project_name: Optional[str] = None,
        filter_project_null: Optional[bool] = None,
    ) -> float:
        logger.debug(f"CSVBackend: get_accounting_entries_for_quota called for {limit_type}.")
        return 0.0 # Placeholder, actual aggregation needed if tests rely on it

    @override
    def insert_usage_limit(self, limit: UsageLimitDTO) -> None:
        logger.debug(f"CSVBackend: insert_usage_limit called with {limit}.")
        # Create a copy to assign ID if it's a Pydantic model, or handle directly
        # For simple dataclass or if direct mutation is fine for mock:
        if hasattr(limit, 'model_copy'): # Pydantic model
             new_limit = limit.model_copy(deep=True)
        else: # Standard dataclass, shallow copy might be enough or direct mutation
            import copy
            new_limit = copy.deepcopy(limit)

        if new_limit.id is None:
            new_limit.id = self._next_id
            self._next_id += 1
        self._mock_limits_entries.append(new_limit)
        # BaseBackend defines this method as returning None.

    @override
    def delete_usage_limit(self, limit_id: int) -> None:
        logger.debug(f"CSVBackend: delete_usage_limit called for id {limit_id}.")
        original_len = len(self._mock_limits_entries)
        self._mock_limits_entries = [l for l in self._mock_limits_entries if l.id != limit_id]
        if len(self._mock_limits_entries) < original_len:
            logger.debug(f"Limit with id {limit_id} removed from mock list.")
        else:
            logger.debug(f"Limit with id {limit_id} not found in mock list.")

    @override
    def initialize_audit_log_schema(self) -> None:
        logger.debug("CSVBackend: initialize_audit_log_schema called (handled in __init__).")
        pass

    @override
    def log_audit_event(self, entry: AuditLogEntry) -> None:
        logger.debug(f"CSVBackend: log_audit_event called with {entry}")
        if entry.id is None:
            entry.id = self._next_id
            self._next_id += 1
        self._mock_audit_entries.append(entry)
    
    @override
    def get_usage_costs(self, user_id: str, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> float:
        logger.debug(f"CSVBackend: get_usage_costs for user {user_id}.")
        return 0.0

    @override
    def get_audit_log_entries(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None,
        app_name: Optional[str] = None, user_name: Optional[str] = None,
        project: Optional[str] = None, log_type: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[AuditLogEntry]:
        logger.debug(f"CSVBackend: get_audit_log_entries called with filters.")
        
        results = self._mock_audit_entries
        if start_date:
            results = [r for r in results if r.timestamp and r.timestamp >= start_date]
        if end_date:
            results = [r for r in results if r.timestamp and r.timestamp < end_date]
        if app_name:
            results = [r for r in results if r.app_name == app_name]
        if user_name:
            results = [r for r in results if r.user_name == user_name]
        if project:
            results = [r for r in results if r.project == project]
        if log_type:
            results = [r for r in results if r.log_type == log_type]
        
        # Sort by timestamp descending (newest first) before applying limit
        results.sort(key=lambda r: r.timestamp if r.timestamp else datetime.min, reverse=True)

        if limit is not None:
            results = results[:limit]
            
        return list(results)
