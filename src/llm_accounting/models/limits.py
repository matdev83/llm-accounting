from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

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

@dataclass
class UsageLimit:
    scope: str
    limit_type: str
    max_value: float
    interval_unit: str
    interval_value: int
    model: Optional[str] = None
    username: Optional[str] = None
    caller_name: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
        if self.updated_at is None:
            self.updated_at = datetime.now(timezone.utc)

    def time_delta(self) -> timedelta:
        interval = int(self.interval_value)
        return {
            TimeInterval.SECOND: timedelta(seconds=interval),
            TimeInterval.MINUTE: timedelta(minutes=interval),
            TimeInterval.HOUR: timedelta(hours=interval),
            TimeInterval.DAY: timedelta(days=interval),
            TimeInterval.WEEK: timedelta(weeks=interval),
            TimeInterval.MONTH: NotImplementedError("TimeDelta for month is not supported. Use QuotaService.get_period_start instead."),
        }[TimeInterval(self.interval_unit)]
