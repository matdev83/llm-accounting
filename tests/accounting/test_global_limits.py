import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from llm_accounting.models import Base
from llm_accounting.models.limits import UsageLimit, LimitScope, LimitType, TimeInterval
from llm_accounting.services.quota_service import QuotaService

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Session = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)
    session = Session()
    yield session
    session.close()

@pytest.fixture
def quota_service(db_session):
    return QuotaService(db_session)

def test_global_limit(quota_service, db_session):
    db_session.add(UsageLimit(
        scope=LimitScope.GLOBAL.value,
        limit_type=LimitType.REQUESTS.value,
        max_value=10,
        interval_unit=TimeInterval.MINUTE.value,
        interval_value=1
    ))
    db_session.commit()

    from llm_accounting.models import APIRequest
    
    # Check and add requests sequentially
    for _ in range(10):
        allowed, _ = quota_service.check_quota("gpt-4", "user1", "app1", 1000, 0.25)
        assert allowed
        db_session.add(APIRequest(
            model="gpt-4",
            username="user1",
            caller_name="app1",
            input_tokens=1000,
            output_tokens=500,
            cost=0.25,
            timestamp=datetime.now(timezone.utc)
        ))
        db_session.commit()
    
    # Add 11th request to exceed limit
    db_session.add(APIRequest(
        model="gpt-4",
        username="user1",
        caller_name="app1",
        input_tokens=1000,
        output_tokens=500,
        cost=0.25,
        timestamp=datetime.now(timezone.utc)
    ))
    db_session.commit()
    
    allowed, message = quota_service.check_quota("gpt-4", "user1", "app1", 1000, 0.25)
    assert not allowed
    assert "GLOBAL limit: 10.00 requests per 1 minute" in message
