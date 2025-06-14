from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional
from dataclasses import dataclass

from sqlalchemy import Column, DateTime, Float, Integer, String, event, DDL
from sqlalchemy.schema import UniqueConstraint

from llm_accounting.models.base import Base


class LimitScope(Enum):
    GLOBAL = "GLOBAL"
    MODEL = "MODEL"
    USER = "USER"
    CALLER = "CALLER"
    PROJECT = "PROJECT"


class LimitType(Enum):
    REQUESTS = "requests"
    INPUT_TOKENS = "input_tokens"
    OUTPUT_TOKENS = "output_tokens"
    TOTAL_TOKENS = "total_tokens"
    COST = "cost"


class TimeInterval(Enum):
    SECOND = "second"
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "monthly"
    SECOND_ROLLING = "second_rolling"
    MINUTE_ROLLING = "minute_rolling"
    HOUR_ROLLING = "hour_rolling"
    DAY_ROLLING = "day_rolling"
    WEEK_ROLLING = "week_rolling"
    MONTH_ROLLING = "monthly_rolling"

    def is_rolling(self) -> bool:
        return self in [
            TimeInterval.SECOND_ROLLING,
            TimeInterval.MINUTE_ROLLING,
            TimeInterval.HOUR_ROLLING,
            TimeInterval.DAY_ROLLING,
            TimeInterval.WEEK_ROLLING,
            TimeInterval.MONTH_ROLLING,
        ]


@dataclass
class UsageLimitDTO:
    scope: str
    limit_type: str
    max_value: float
    interval_unit: str
    interval_value: int
    model: Optional[str] = None
    username: Optional[str] = None
    caller_name: Optional[str] = None
    project_name: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UsageLimit(Base):
    __tablename__ = "usage_limits"
    __table_args__ = (
        UniqueConstraint(
            "scope",
            "limit_type",
            "model",
            "username",
            "caller_name",
            "project_name",
            name="_unique_limit_constraint",
        ),
        # Index("ix_usage_limits_project_name", "project_name"), # Removed to be handled by event listener
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
    project_name = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self):
        return (
            f"<UsageLimit(id={self.id}, scope='{self.scope}', type='{self.limit_type}', "
            f"max_value={self.max_value}, project='{self.project_name}')>"
        )

    # TODO: Vulture - Dead code? Verify if used externally or planned for future use before removing.
    # def time_delta(self) -> timedelta:
    #     interval_val = int(self._interval_value)
    #     unit = str(self._interval_unit)
    #     delta_map = {
    #         TimeInterval.SECOND.value: timedelta(seconds=interval_val),
    #         TimeInterval.MINUTE.value: timedelta(minutes=interval_val),
    #         TimeInterval.HOUR.value: timedelta(hours=interval_val),
    #         TimeInterval.DAY.value: timedelta(days=interval_val),
    #         TimeInterval.WEEK.value: timedelta(weeks=interval_val),
    #     }
    #     if unit == TimeInterval.MONTH.value:
    #         raise NotImplementedError(
    #             "Exact timedelta for 'month' is complex. QuotaService should handle period start for monthly limits."
    #         )
    #
    #     if unit not in delta_map:
    #         raise ValueError(f"Unsupported time interval unit: {unit}")
    #
    #     return delta_map[unit]


# Event listener to create the index with IF NOT EXISTS for SQLite
for _idx_col in ["project_name", "model", "username", "caller_name"]:
    event.listen(
        UsageLimit.__table__,
        "after_create",
        DDL(
            f"CREATE INDEX IF NOT EXISTS ix_usage_limits_{_idx_col} ON usage_limits ({_idx_col})"
        ).execute_if(dialect="sqlite"),
    )
