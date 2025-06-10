from sqlalchemy import Column, DateTime, Integer, String

from llm_accounting.models.base import Base


class AuditLogEntryModel(Base):
    __tablename__ = "audit_log_entries"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False)
    app_name = Column(String, nullable=False)
    user_name = Column(String, nullable=False)
    model = Column(String, nullable=False)
    prompt_text = Column(String, nullable=True)
    response_text = Column(String, nullable=True)
    remote_completion_id = Column(String, nullable=True)
    project = Column(String, nullable=True)
    session = Column(String, nullable=True)
    log_type = Column(String, nullable=False)

    def __repr__(self):
        return (
            f"<AuditLogEntryModel(id={self.id}, timestamp='{self.timestamp}', app_name='{self.app_name}', "
            f"user_name='{self.user_name}', model='{self.model}', project='{self.project}')>"
        )
