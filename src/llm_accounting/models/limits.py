from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column
from llm_accounting.models import Base

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
    __tablename__ = "usage_limits"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    scope: Mapped[str] = mapped_column(String(20))
    limit_type: Mapped[str] = mapped_column(String(20))
    model: Mapped[Optional[str]] = mapped_column(String(50))
    username: Mapped[Optional[str]] = mapped_column(String(50))
    caller_name: Mapped[Optional[str]] = mapped_column(String(50))
    max_value: Mapped[float] = mapped_column(Numeric(15, 6))
    interval_unit: Mapped[str] = mapped_column(String(10))
    interval_value: Mapped[int] = mapped_column(Integer())
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    def time_delta(self) -> timedelta:
        # Get the integer value from the SQLAlchemy column
        interval = int(self.interval_value)
        return {
            TimeInterval.SECOND: timedelta(seconds=interval),
            TimeInterval.MINUTE: timedelta(minutes=interval),
            TimeInterval.HOUR: timedelta(hours=interval),
            TimeInterval.DAY: timedelta(days=interval),
            TimeInterval.WEEK: timedelta(weeks=interval),
            TimeInterval.MONTH: timedelta(days=30*interval),
        }[TimeInterval(self.interval_unit)]
