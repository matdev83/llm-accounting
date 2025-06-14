from sqlalchemy import Column, Integer, String

from llm_accounting.models.base import Base


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)

    def __repr__(self) -> str:
        return f"<Project(id={self.id}, name='{self.name}')>"
