from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, DateTime, Float, Integer, String

from llm_accounting.models.base import Base

# Removed: from sqlalchemy.ext.declarative import declarative_base # Redundant


class APIRequest(Base):
    __tablename__ = "api_requests"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    model = Column(String, nullable=False)
    username = Column(String, nullable=False)
    caller_name = Column(String, nullable=False)
    input_tokens = Column(Integer, nullable=False)
    output_tokens = Column(Integer, nullable=False)
    cost = Column(Float, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __init__(
        self,
        model: str,
        username: str,
        caller_name: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        timestamp: Optional[datetime] = None,
        id: Optional[int] = None,
    ):
        self.model = model
        self.username = username
        self.caller_name = caller_name
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cost = cost
        self.timestamp = (
            timestamp if timestamp is not None else datetime.now(timezone.utc)
        )
        self.id = id

    def __repr__(self):
        return f"<APIRequest(id={self.id}, model='{self.model}', cost={self.cost})>"
