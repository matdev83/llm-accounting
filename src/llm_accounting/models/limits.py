from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.schema import UniqueConstraint

from llm_accounting.models.base import Base

class LimitScope(Enum):
    GLOBAL = "global"
    MODEL = "model"
    USER = "user"
    CALLER = "caller"

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
    MONTH = "month"

class UsageLimit(Base):
    __tablename__ = 'usage_limits'
    __table_args__ = (UniqueConstraint('scope', 'limit_type', 'model', 'username', 'caller_name', name='_unique_limit_constraint'),)

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
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __init__(self, scope: str, limit_type: str, max_value: float, interval_unit: str, interval_value: int, model: Optional[str] = None, username: Optional[str] = None, caller_name: Optional[str] = None, id: Optional[int] = None, created_at: Optional[datetime] = None, updated_at: Optional[datetime] = None):
        self.scope = scope
        self.limit_type = limit_type
        self.max_value = max_value
        self.interval_unit = interval_unit
        self.interval_value = interval_value
        self.model = model
        self.username = username
        self.caller_name = caller_name
        self.id = id
        self.created_at = created_at if created_at is not None else datetime.now(timezone.utc)
        self.updated_at = updated_at if updated_at is not None else datetime.now(timezone.utc)

    def __repr__(self):
        return f"<UsageLimit(id={self.id}, scope='{self.scope}', type='{self.limit_type}', max_value={self.max_value})>"

    def time_delta(self) -> timedelta:
        interval = int(self.interval_value)
        return {
            TimeInterval.SECOND.value: timedelta(seconds=interval),
            TimeInterval.MINUTE.value: timedelta(minutes=interval),
            TimeInterval.HOUR.value: timedelta(hours=interval),
            TimeInterval.DAY.value: timedelta(days=interval),
            TimeInterval.WEEK.value: timedelta(weeks=interval),
            TimeInterval.MONTH.value: NotImplementedError("TimeDelta for month is not supported. Use QuotaService.get_period_start instead."),
        }[self.interval_unit]
