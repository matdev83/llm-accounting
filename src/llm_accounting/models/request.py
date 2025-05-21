from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Numeric
from llm_accounting.models import Base

class APIRequest(Base):
    __tablename__ = "api_requests"
    
    id = Column(Integer, primary_key=True)
    model = Column(String(50), nullable=False)
    username = Column(String(50), nullable=False)
    caller_name = Column(String(50), nullable=False)
    input_tokens = Column(Integer, nullable=False)
    output_tokens = Column(Integer, nullable=False)
    cost = Column(Numeric(15, 6), nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
