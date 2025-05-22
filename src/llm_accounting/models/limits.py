from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional

from sqlalchemy import Column, DateTime, Float, Integer, String
from sqlalchemy.schema import UniqueConstraint

from llm_accounting.models.base import Base


class LimitScope(Enum):
    GLOBAL = "GLOBAL"
    MODEL = "MODEL"
    USER = "USER"
    CALLER = "CALLER"


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
            name="_unique_limit_constraint",
        ),
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
        self.id = id
        self.created_at = (
            created_at if created_at is not None else datetime.now(timezone.utc)
        )
        self.updated_at = (
            updated_at if updated_at is not None else datetime.now(timezone.utc)
        )

    def __repr__(self):
        return f"<UsageLimit(id={self.id}, scope='{self.scope}', type='{self.limit_type}', max_value={self.max_value})>"

    def time_delta(self) -> timedelta:
        # Access the instance values directly from initialization
        interval_val = int(self._interval_value)
        unit = str(self._interval_unit)
        return {
            TimeInterval.SECOND.value: timedelta(seconds=interval_val),
            TimeInterval.MINUTE.value: timedelta(minutes=interval_val),
            TimeInterval.HOUR.value: timedelta(hours=interval_val),
            TimeInterval.DAY.value: timedelta(days=interval_val),
            TimeInterval.WEEK.value: timedelta(weeks=interval_val),
            TimeInterval.MONTH.value: NotImplementedError(
                "TimeDelta for month is not supported. Use QuotaService.get_period_start instead."
            ),
        }[unit]
