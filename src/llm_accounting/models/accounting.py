from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String

from llm_accounting.models.base import Base


class AccountingEntry(Base):
    __tablename__ = "accounting_entries"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    model = Column(String, nullable=False)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    local_prompt_tokens = Column(Integer, nullable=True)
    local_completion_tokens = Column(Integer, nullable=True)
    local_total_tokens = Column(Integer, nullable=True)
    project = Column(String, nullable=True)
    cost = Column(Float, nullable=False)
    execution_time = Column(Float, nullable=False)
    caller_name = Column(String, nullable=True)
    username = Column(String, nullable=True)
    session = Column(String, nullable=True)
    cached_tokens = Column(Integer, nullable=False, default=0)
    reasoning_tokens = Column(Integer, nullable=False, default=0)

    def __repr__(self):
        return (
            f"<AccountingEntry(id={self.id}, timestamp='{self.timestamp}', model='{self.model}', "
            f"project='{self.project}', cost={self.cost})>"
        )
