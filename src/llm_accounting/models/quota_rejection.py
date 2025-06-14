from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Integer, String

from llm_accounting.models.base import Base


class QuotaRejection(Base):
    __tablename__ = "quota_rejections"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    session = Column(String, nullable=False)
    rejection_message = Column(String, nullable=False)

    def __repr__(self) -> str:
        return f"<QuotaRejection(id={self.id}, session='{self.session}')>"
