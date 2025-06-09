from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime

from .base import Base

class User(Base):
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_name = Column(String(255), nullable=False, unique=True)
    ou_name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_enabled_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_disabled_at = Column(DateTime, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, user_name='{self.user_name}', enabled={self.enabled})>"
