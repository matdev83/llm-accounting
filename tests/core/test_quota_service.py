from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from llm_accounting.models import Base
from llm_accounting.models.limits import (LimitScope, LimitType, TimeInterval,
                                          UsageLimit)
from llm_accounting.services.quota_service import QuotaService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Session = sessionmaker(bind=engine)
    from llm_accounting.models import Base
    Base.metadata.create_all(engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def quota_service(db_session):
    return QuotaService(db_session)
