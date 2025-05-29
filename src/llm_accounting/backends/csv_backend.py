import csv
import os
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import asdict # Import asdict

from llm_accounting.backends.base import BaseBackend
from llm_accounting.backends.base import AuditLogEntry, UsageEntry, UsageStats
from llm_accounting.models.limits import UsageLimitDTO, LimitScope, LimitType

# Aliases for internal consistency if old name is used
AccountingEntry = UsageEntry 
PeriodStats = UsageStats     
UsageLimitScope = LimitScope 


class CSVBackend(BaseBackend):
    DEFAULT_DATA_DIR = "data/"
    ACCOUNTING_ENTRIES_FILE = "accounting_entries.csv"
    USAGE_LIMITS_FILE = "usage_limits.csv"
    AUDIT_LOG_ENTRIES_FILE = "audit_log_entries.csv"

    ACCOUNTING_FIELDNAMES = [
        "id", "model", "prompt_tokens", "completion_tokens", "total_tokens",
        "local_prompt_tokens", "local_completion_tokens", "local_total_tokens",
        "cost", "execution_time", "timestamp", "caller_name", "username",
        "project", "cached_tokens", "reasoning_tokens"
    ]
    USAGE_LIMITS_FIELDNAMES = [
        "id", "scope", "limit_type", "model", "username", "caller_name",
        "project_name", "max_value", "interval_unit", "interval_value",
        "created_at", "updated_at"
    ]
    AUDIT_LOG_FIELDNAMES = [
        "id", "timestamp", "app_name", "user_name", "model", "prompt_text",
        "response_text", "remote_completion_id", "project", "log_type"
    ]

    def __init__(self, csv_data_dir: Optional[str] = None):
        self.data_dir = csv_data_dir or self.DEFAULT_DATA_DIR
        self.accounting_file_path = os.path.join(self.data_dir, self.ACCOUNTING_ENTRIES_FILE)
        self.usage_limits_file_path = os.path.join(self.data_dir, self.USAGE_LIMITS_FILE)
        self.audit_log_file_path = os.path.join(self.data_dir, self.AUDIT_LOG_ENTRIES_FILE)
        self._ensure_connected()

    def _ensure_connected(self):
        if not os.path.exists(self.data_dir):
            try:
                os.makedirs(self.data_dir)
            except OSError as e:
                raise IOError(f"Could not create data directory '{self.data_dir}': {e}")
        if not os.path.isdir(self.data_dir) or not os.access(self.data_dir, os.W_OK):
            raise IOError(f"Data directory '{self.data_dir}' is not a writable directory.")

    def initialize(self):
        self._ensure_connected()
        for filepath, fieldnames in [
            (self.accounting_file_path, self.ACCOUNTING_FIELDNAMES),
            (self.usage_limits_file_path, self.USAGE_LIMITS_FIELDNAMES),
            (self.audit_log_file_path, self.AUDIT_LOG_FIELDNAMES),
        ]:
            if not os.path.exists(filepath):
                try:
                    with open(filepath, "w", newline="") as csvfile:
                        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                        writer.writeheader()
                except IOError as e:
                    raise IOError(f"Could not initialize file '{filepath}': {e}")

    def purge(self):
        self._ensure_connected()
        for filepath, fieldnames in [
            (self.accounting_file_path, self.ACCOUNTING_FIELDNAMES),
            (self.usage_limits_file_path, self.USAGE_LIMITS_FIELDNAMES),
            (self.audit_log_file_path, self.AUDIT_LOG_FIELDNAMES),
        ]:
            try:
                with open(filepath, "w", newline="") as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
            except IOError as e:
                raise IOError(f"Could not purge file '{filepath}': {e}")

    def _get_next_id(self, filepath: str) -> int:
        try:
            max_id = 0
            if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
                return 1
            with open(filepath, "r", newline="") as csvfile:
                reader = csv.DictReader(csvfile)
                if not reader.fieldnames or "id" not in reader.fieldnames:
                    return 1
                has_rows = False
                for row in reader:
                    has_rows = True
                    row_id_str = row.get("id")
                    if row_id_str and row_id_str.isdigit():
                        max_id = max(max_id, int(row_id_str))
                return max_id + 1 if has_rows else 1
        except FileNotFoundError: return 1
        except Exception: return 1

    def _write_row(self, filepath: str, fieldnames: List[str], row_dict: Dict[str, Any]):
        self._ensure_connected()
        file_exists = os.path.exists(filepath)
        file_is_empty = not file_exists or os.path.getsize(filepath) == 0
        try:
            with open(filepath, "a", newline="") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                if file_is_empty:
                    writer.writeheader()
                writer.writerow(row_dict)
        except IOError as e:
            raise IOError(f"Could not write to file '{filepath}': {e}")

    def insert_usage(self, entry: UsageEntry) -> None:
        entry_dict = asdict(entry) # CHANGED to asdict
        entry_dict["id"] = self._get_next_id(self.accounting_file_path)
        if entry.timestamp:
            entry_dict["timestamp"] = entry.timestamp.isoformat()
        for key, value in entry_dict.items():
            if value is None: entry_dict[key] = ""
        self._write_row(self.accounting_file_path, self.ACCOUNTING_FIELDNAMES, entry_dict)

    def insert_usage_limit(self, limit: UsageLimitDTO) -> UsageLimitDTO:
        limit.id = self._get_next_id(self.usage_limits_file_path)
        now = datetime.now()
        limit.created_at = limit.created_at or now
        limit.updated_at = now 
        limit_dict = asdict(limit) # Changed to asdict as per instruction
        if limit.scope: limit_dict["scope"] = limit.scope.value
        if limit.created_at: limit_dict["created_at"] = limit.created_at.isoformat()
        if limit.updated_at: limit_dict["updated_at"] = limit.updated_at.isoformat()
        for key, value in limit_dict.items():
            if value is None: limit_dict[key] = ""
        self._write_row(self.usage_limits_file_path, self.USAGE_LIMITS_FIELDNAMES, limit_dict)
        return limit

    def log_audit_event(self, entry: AuditLogEntry) -> None:
        entry_dict = asdict(entry) # CHANGED to asdict
        entry_dict["id"] = self._get_next_id(self.audit_log_file_path)
        if entry.timestamp: entry_dict["timestamp"] = entry.timestamp.isoformat()
        # entry.log_type is already a string
        if entry.log_type is None: entry_dict["log_type"] = ""
        
        for key, value in entry_dict.items():
            if value is None: entry_dict[key] = ""
        self._write_row(self.audit_log_file_path, self.AUDIT_LOG_FIELDNAMES, entry_dict)

    def _read_rows(self, filepath: str) -> List[Dict[str, str]]:
        self._ensure_connected()
        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0: return []
        try:
            with open(filepath, "r", newline="") as csvfile:
                reader = csv.DictReader(csvfile)
                if not reader.fieldnames: return []
                return [row for row in reader]
        except FileNotFoundError: return []
        except IOError as e: raise IOError(f"Could not read file '{filepath}': {e}")

    def get_usage_limits(
        self,
        scope: Optional[LimitScope] = None,
        model: Optional[str] = None,
        username: Optional[str] = None,
        caller_name: Optional[str] = None,
        project_name: Optional[str] = None,
        filter_project_null: Optional[bool] = None,
        filter_username_null: Optional[bool] = None,
        filter_caller_name_null: Optional[bool] = None,
    ) -> List[UsageLimitDTO]:
        limits = []
        all_rows = self._read_rows(self.usage_limits_file_path)
        for row in all_rows:
            if scope and row.get("scope") != scope.value: continue
            if model and row.get("model") and row.get("model") != model: continue
            if filter_username_null is True and row.get("username") != "": continue
            if filter_username_null is False and row.get("username") == "": continue
            if username and row.get("username") != username : continue
            if filter_caller_name_null is True and row.get("caller_name") != "": continue
            if filter_caller_name_null is False and row.get("caller_name") == "": continue
            if caller_name and row.get("caller_name") != caller_name: continue
            if filter_project_null is True and row.get("project_name") != "": continue
            if filter_project_null is False and row.get("project_name") == "": continue
            if project_name and row.get("project_name") != project_name: continue

            row_scope_str = row.get("scope")
            row_scope = LimitScope(row_scope_str) if row_scope_str else None
            created_at = datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None
            updated_at = datetime.fromisoformat(row["updated_at"]) if row.get("updated_at") else None
            max_val = int(row["max_value"]) if row.get("max_value", "").isdigit() else None
            int_val = int(row["interval_value"]) if row.get("interval_value", "").isdigit() else None
            id_val = int(row["id"]) if row.get("id", "").isdigit() else 0
            limits.append(UsageLimitDTO(
                id=id_val, scope=row_scope, limit_type=row.get("limit_type") or "",
                model=row.get("model") or None, username=row.get("username") or None,
                caller_name=row.get("caller_name") or None, project_name=row.get("project_name") or None,
                max_value=max_val, interval_unit=row.get("interval_unit") or None,
                interval_value=int_val, created_at=created_at, updated_at=updated_at,
            ))
        return limits

    def delete_usage_limit(self, limit_id: int) -> None:
        self._ensure_connected()
        if not os.path.exists(self.usage_limits_file_path): return
        rows_to_keep = []
        deleted = False
        try:
            with open(self.usage_limits_file_path, "r", newline="") as csvfile:
                reader = csv.DictReader(csvfile)
                if not reader.fieldnames or "id" not in reader.fieldnames: return
                for row in reader:
                    if row.get("id","").isdigit() and int(row["id"]) == limit_id: deleted = True
                    else: rows_to_keep.append(row)
        except IOError as e: raise IOError(f"Error reading usage limits file for deletion: {e}")
        if deleted:
            try:
                with open(self.usage_limits_file_path, "w", newline="") as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=self.USAGE_LIMITS_FIELDNAMES)
                    writer.writeheader()
                    writer.writerows(rows_to_keep)
            except IOError as e: raise IOError(f"Error writing usage limits file after deletion: {e}")

    def get_period_stats( self, start: datetime, end: datetime, model: Optional[str] = None, username: Optional[str] = None, caller_name: Optional[str] = None, project: Optional[str] = None ) -> UsageStats:
        all_rows = self._read_rows(self.accounting_file_path)
        p_tok, c_tok, t_tok, cost, exec_t = 0,0,0,0.0,0.0
        lp_tok, lc_tok, lt_tok, cach_tok, reas_tok = 0,0,0,0,0
        for row in all_rows:
            ts_str = row.get("timestamp")
            if not ts_str: continue
            try: entry_ts = datetime.fromisoformat(ts_str)
            except ValueError: continue
            if not (start <= entry_ts < end): continue
            if model and row.get("model") != model: continue
            if username and row.get("username") != username: continue
            if caller_name and row.get("caller_name") != caller_name: continue
            if project and row.get("project") != project: continue
            p_tok+=self._to_int_or_zero(row.get("prompt_tokens")); c_tok+=self._to_int_or_zero(row.get("completion_tokens")); t_tok+=self._to_int_or_zero(row.get("total_tokens")); cost+=self._to_float_or_zero(row.get("cost")); exec_t+=self._to_float_or_zero(row.get("execution_time"))
            lp_tok+=self._to_int_or_zero(row.get("local_prompt_tokens")); lc_tok+=self._to_int_or_zero(row.get("local_completion_tokens")); lt_tok+=self._to_int_or_zero(row.get("local_total_tokens")); cach_tok+=self._to_int_or_zero(row.get("cached_tokens")); reas_tok+=self._to_int_or_zero(row.get("reasoning_tokens"))
        return UsageStats( sum_prompt_tokens=p_tok, sum_completion_tokens=c_tok, sum_total_tokens=t_tok, sum_cost=cost, sum_execution_time=exec_t, sum_local_prompt_tokens=lp_tok, sum_local_completion_tokens=lc_tok, sum_local_total_tokens=lt_tok) # Removed avg fields and num_requests

    def _to_int_or_none(self, val_str: Optional[str]) -> Optional[int]:
        if val_str is None or val_str == "" or not val_str.isdigit(): return None
        return int(val_str)

    def _to_float_or_none(self, val_str: Optional[str]) -> Optional[float]:
        if val_str is None or val_str == "": return None
        try: return float(val_str)
        except ValueError: return None
        
    def _to_int_or_zero(self, val_str: Optional[str]) -> int:
        res = self._to_int_or_none(val_str)
        return res if res is not None else 0

    def _to_float_or_zero(self, val_str: Optional[str]) -> float:
        res = self._to_float_or_none(val_str)
        return res if res is not None else 0.0

    def tail( self, n: int = 10, model: Optional[str] = None, username: Optional[str] = None, caller_name: Optional[str] = None, project: Optional[str] = None ) -> List[UsageEntry]:
        if n <= 0: return []
        all_rows = self._read_rows(self.accounting_file_path)
        filtered_entries = []
        for row in all_rows:
            if model and row.get("model") and row.get("model") != model: continue
            if username and row.get("username") and row.get("username") != username: continue
            if caller_name and row.get("caller_name") and row.get("caller_name") != caller_name: continue
            if project and row.get("project") and row.get("project") != project: continue
            ts = datetime.fromisoformat(row["timestamp"]) if row.get("timestamp") else None
            
            # Construct UsageEntry fields carefully.
            entry_data = {
                "id": self._to_int_or_none(row.get("id")), # Ensure id is populated
                "model": row.get("model") or "",
                "prompt_tokens": self._to_int_or_none(row.get("prompt_tokens")),
                "completion_tokens": self._to_int_or_none(row.get("completion_tokens")),
                "total_tokens": self._to_int_or_none(row.get("total_tokens")),
                "local_prompt_tokens": self._to_int_or_none(row.get("local_prompt_tokens")),
                "local_completion_tokens": self._to_int_or_none(row.get("local_completion_tokens")),
                "local_total_tokens": self._to_int_or_none(row.get("local_total_tokens")),
                "cost": self._to_float_or_none(row.get("cost")) or 0.0, # Ensure cost is float
                "execution_time": self._to_float_or_none(row.get("execution_time")) or 0.0, # Ensure exec time is float
                "timestamp": ts,
                "caller_name": row.get("caller_name") or None,
                "username": row.get("username") or None,
                "project": row.get("project") or None,
                "cached_tokens": self._to_int_or_zero(row.get("cached_tokens")),
                "reasoning_tokens": self._to_int_or_zero(row.get("reasoning_tokens"))
            }
            filtered_entries.append(UsageEntry(**entry_data))
        return filtered_entries[-n:]

    def get_audit_log_entries( self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None, app_name: Optional[str] = None, user_name: Optional[str] = None, project: Optional[str] = None, log_type: Optional[str] = None, limit: Optional[int] = None ) -> List[AuditLogEntry]:
        all_rows = self._read_rows(self.audit_log_file_path)
        filtered_entries = []
        for row_data in all_rows:
            if log_type and row_data.get("log_type") != log_type: continue
            if user_name and row_data.get("user_name") != user_name: continue
            if app_name and row_data.get("app_name") != app_name: continue
            if project and row_data.get("project") != project: continue
            ts_str = row_data.get("timestamp")
            entry_ts = datetime.fromisoformat(ts_str) if ts_str else None
            if entry_ts:
                if start_date and entry_ts < start_date: continue
                if end_date and entry_ts >= end_date: continue # end_date is exclusive upper bound
            elif start_date or end_date: continue
            
            audit_entry_data = {
                "id": self._to_int_or_none(row_data.get("id")), # id is part of AuditLogEntry
                "timestamp": entry_ts,
                "app_name": row_data.get("app_name") or "", # app_name is not Optional in DTO
                "user_name": row_data.get("user_name") or "", # user_name is not Optional
                "model": row_data.get("model") or "",       # model is not Optional
                "prompt_text": row_data.get("prompt_text"),
                "response_text": row_data.get("response_text"),
                "remote_completion_id": row_data.get("remote_completion_id"),
                "project": row_data.get("project"),
                "log_type": row_data.get("log_type") or "" # log_type is not Optional
            }
            # Ensure non-optional fields have defaults if row_data.get() returns None
            if audit_entry_data["timestamp"] is None: audit_entry_data["timestamp"] = datetime.min # Or handle error
            
            filtered_entries.append(AuditLogEntry(**audit_entry_data))
        
        filtered_entries.sort(key=lambda x: x.timestamp or datetime.min, reverse=True)
        return filtered_entries[:limit] if limit is not None else filtered_entries

    def close(self) -> None:
        pass

    def execute_query(self, query: str) -> list[dict]:
        raise NotImplementedError("CSVBackend does not support arbitrary SQL queries.")

    def get_accounting_entries_for_quota( self, start_time: datetime, limit_type: LimitType, model: Optional[str] = None, username: Optional[str] = None, caller_name: Optional[str] = None, project_name: Optional[str] = None, filter_project_null: Optional[bool] = None, ) -> float:
        all_rows = self._read_rows(self.accounting_file_path)
        total_value = 0.0
        num_requests = 0
        for row in all_rows:
            ts_str = row.get("timestamp")
            if not ts_str: continue
            try: entry_ts = datetime.fromisoformat(ts_str)
            except ValueError: continue
            if not (start_time <= entry_ts): continue
            if model and row.get("model") != model: continue
            if username and row.get("username") != username: continue
            if caller_name and row.get("caller_name") != caller_name: continue
            if filter_project_null is True and (row.get("project") is not None and row.get("project") != "") : continue
            if filter_project_null is False and (row.get("project") is None or row.get("project") == ""): continue
            if project_name and row.get("project") != project_name: continue

            num_requests += 1
            if limit_type == LimitType.COST: total_value += self._to_float_or_zero(row.get("cost"))
            elif limit_type == LimitType.TOTAL_TOKENS: total_value += self._to_int_or_zero(row.get("total_tokens"))
            elif limit_type == LimitType.PROMPT_TOKENS: total_value += self._to_int_or_zero(row.get("prompt_tokens"))
            elif limit_type == LimitType.COMPLETION_TOKENS: total_value += self._to_int_or_zero(row.get("completion_tokens"))
        if limit_type == LimitType.REQUESTS: return float(num_requests)
        return total_value

    def get_model_stats(self, start: datetime, end: datetime) -> List[Tuple[str, UsageStats]]:
        all_rows = self._read_rows(self.accounting_file_path)
        model_data: Dict[str, Dict[str, Any]] = {}
        for row in all_rows:
            ts_str = row.get("timestamp")
            if not ts_str: continue
            try: entry_ts = datetime.fromisoformat(ts_str)
            except ValueError: continue
            if not (start <= entry_ts < end): continue
            current_model = row.get("model", "unknown_model")
            if not current_model: current_model = "unknown_model"
            if current_model not in model_data:
                model_data[current_model] = {
                    "sum_prompt_tokens": 0, "sum_completion_tokens": 0, "sum_total_tokens": 0,
                    "sum_cost": 0.0, "sum_execution_time": 0.0,
                    "sum_local_prompt_tokens": 0, "sum_local_completion_tokens": 0, "sum_local_total_tokens": 0,
                }
            model_data[current_model]["sum_prompt_tokens"] += self._to_int_or_zero(row.get("prompt_tokens"))
            model_data[current_model]["sum_completion_tokens"] += self._to_int_or_zero(row.get("completion_tokens"))
            model_data[current_model]["sum_total_tokens"] += self._to_int_or_zero(row.get("total_tokens"))
            model_data[current_model]["sum_cost"] += self._to_float_or_zero(row.get("cost"))
            model_data[current_model]["sum_execution_time"] += self._to_float_or_zero(row.get("execution_time"))
            model_data[current_model]["sum_local_prompt_tokens"] += self._to_int_or_zero(row.get("local_prompt_tokens"))
            model_data[current_model]["sum_local_completion_tokens"] += self._to_int_or_zero(row.get("local_completion_tokens"))
            model_data[current_model]["sum_local_total_tokens"] += self._to_int_or_zero(row.get("local_total_tokens"))
        result: List[Tuple[str, UsageStats]] = []
        for model_name, stats in model_data.items():
            result.append((model_name, UsageStats(**stats)))
        return result

    def get_model_rankings(self, start: datetime, end: datetime) -> Dict[str, List[Tuple[str, Any]]]:
        raise NotImplementedError("CSVBackend does not support model rankings.")

    def initialize_audit_log_schema(self) -> None:
        pass
