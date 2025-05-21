import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from llm_accounting.models import Base, APIRequest
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

def test_user_caller_combination(quota_service, db_session):
    db_session.add(UsageLimit(
        scope=LimitScope.CALLER.value,
        username="user1",
        caller_name="app1",
        limit_type=LimitType.REQUESTS.value,
        max_value=3,
        interval_unit=TimeInterval.DAY.value,
        interval_value=1
    ))
    db_session.commit()

    from llm_accounting.models import APIRequest
    
    # Make 3 allowed requests
    for _ in range(3):
        # Check quota before adding request
        allowed, _ = quota_service.check_quota("gpt-3", "user1", "app1", 1000, 0.25)
        assert allowed
        # Track the allowed request
        db_session.add(APIRequest(
            model="gpt-3",
            username="user1",
            caller_name="app1",
            input_tokens=1000,
            output_tokens=500,
            cost=0.25,
            timestamp=datetime.now(timezone.utc)
        ))
        db_session.commit()
    
    # Make 4th request that should be blocked
    db_session.add(APIRequest(
        model="gpt-3",
        username="user1",
        caller_name="app1",
        input_tokens=1000,
        output_tokens=500,
        cost=0.25,
        timestamp=datetime.now(timezone.utc)
    ))
    db_session.commit()
    allowed, message = quota_service.check_quota("gpt-3", "user1", "app1", 1000, 0.25)
    assert not allowed
    assert "CALLER limit: 3.00 requests per 1 day" in message
