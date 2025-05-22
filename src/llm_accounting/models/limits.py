from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import Column, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
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
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String, nullable=False)
    limit_type: Mapped[str] = mapped_column(String, nullable=False)
    max_value: Mapped[float] = mapped_column(Float, nullable=False)
    interval_unit: Mapped[str] = mapped_column(String, nullable=False)
    interval_value: Mapped[int] = mapped_column(Integer, nullable=False)
    model: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    username: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    caller_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


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
            TimeInterval.MONTH.value: NotImplementedError(
                "TimeDelta for month is not supported. Use QuotaService.get_period_start instead."
            ),
        }[self.interval_unit]
