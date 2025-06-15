from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Boolean

from llm_accounting.models.base import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_name = Column(String(255), nullable=False, unique=True)
    ou_name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    # These fields are used by some migrations and tests; keep them for now.
    last_enabled_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_disabled_at = Column(DateTime, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, user_name='{self.user_name}', enabled={self.enabled})>"
