from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional

from sqlalchemy import Column, DateTime, Float, Integer, String, Index
from sqlalchemy.schema import UniqueConstraint

from llm_accounting.models.base import Base


class LimitScope(Enum):
    GLOBAL = "GLOBAL"
    MODEL = "MODEL"
    USER = "USER"
    CALLER = "CALLER"
    PROJECT = "PROJECT" # New scope


class LimitType(Enum):
    REQUESTS = "requests"
    INPUT_TOKENS = "input_tokens"
    OUTPUT_TOKENS = "output_tokens"
    COST = "cost"


class TimeInterval(Enum):
    SECOND = "second"
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "monthly"


class UsageLimit(Base):
    __tablename__ = "usage_limits"
    __table_args__ = (
        UniqueConstraint(
            "scope",
            "limit_type",
            "model",
            "username",
            "caller_name",
            "project_name", # Added project_name
            name="_unique_limit_constraint",
        ),
        # Adding an index for faster lookups involving project_name
        Index("ix_usage_limits_project_name", "project_name"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    scope = Column(String, nullable=False)
    limit_type = Column(String, nullable=False)
    max_value = Column(Float, nullable=False)
    interval_unit = Column(String, nullable=False)
    interval_value = Column(Integer, nullable=False)
    model = Column(String, nullable=True)
    username = Column(String, nullable=True)
    caller_name = Column(String, nullable=True)
    project_name = Column(String, nullable=True) # New column for project_name
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __init__(
        self,
        scope: Any,  # Can be str or LimitScope enum
        limit_type: Any,  # Can be str or LimitType enum
        max_value: float,
        interval_unit: Any,  # Can be str or TimeInterval enum
        interval_value: int,
        model: Optional[str] = None,
        username: Optional[str] = None,
        caller_name: Optional[str] = None,
        project_name: Optional[str] = None, # New field
        id: Optional[int] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.scope = scope.value if isinstance(scope, LimitScope) else scope
        self.limit_type = limit_type.value if isinstance(limit_type, LimitType) else limit_type
        self.max_value = max_value
        self._interval_unit = interval_unit.value if isinstance(interval_unit, TimeInterval) else interval_unit
        self._interval_value = interval_value
        # SQLAlchemy column mappings
        self.interval_unit = self._interval_unit
        self.interval_value = self._interval_value
        self.model = model
        self.username = username
        self.caller_name = caller_name
        self.project_name = project_name # Assign new field
        self.id = id
        self.created_at = (
            created_at if created_at is not None else datetime.now(timezone.utc)
        )
        self.updated_at = (
            updated_at if updated_at is not None else datetime.now(timezone.utc)
        )

    def __repr__(self):
        return (
            f"<UsageLimit(id={self.id}, scope='{self.scope}', type='{self.limit_type}', "
            f"max_value={self.max_value}, project='{self.project_name}')>"
        )


    def time_delta(self) -> timedelta:
        # Access the instance values directly from initialization
        interval_val = int(self._interval_value)
        unit = str(self._interval_unit)
        delta_map = {
            TimeInterval.SECOND.value: timedelta(seconds=interval_val),
            TimeInterval.MINUTE.value: timedelta(minutes=interval_val),
            TimeInterval.HOUR.value: timedelta(hours=interval_val),
            TimeInterval.DAY.value: timedelta(days=interval_val),
            TimeInterval.WEEK.value: timedelta(weeks=interval_val),
        }
        if unit == TimeInterval.MONTH.value:
            # This is a simplified approach for timedelta for months.
            # A more accurate approach would use calendar logic (e.g., dateutil.relativedelta)
            # but for the purpose of quota checks, an approximation of 30 days is often used.
            # Or, handle month-based calculations specifically where it's called.
            # For now, raising NotImplementedError if exact timedelta is needed.
            # The QuotaService likely handles "monthly" by calculating the start of the period.
            raise NotImplementedError(
                "Exact timedelta for 'month' is complex. QuotaService should handle period start for monthly limits."
            )
        
        if unit not in delta_map:
            raise ValueError(f"Unsupported time interval unit: {unit}")
            
        return delta_map[unit]
