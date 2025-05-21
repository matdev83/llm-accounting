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

def test_multiple_limit_types(quota_service, db_session):
    db_session.add_all([
        UsageLimit(
            scope=LimitScope.USER.value,
            username="user2",
            limit_type=LimitType.INPUT_TOKENS.value,
            max_value=10000,
            interval_unit=TimeInterval.DAY.value,
            interval_value=1
        ),
        UsageLimit(
            scope=LimitScope.USER.value,
            username="user2",
            limit_type=LimitType.COST.value,
            max_value=50.00,
            interval_unit=TimeInterval.WEEK.value,
            interval_value=1
        )
    ])
    db_session.commit()

    # Test token limit
    allowed, message = quota_service.check_quota("gpt-4", "user2", "app2", 15000, 0.0)
    assert not allowed
    assert "USER limit: 10000.00 input_tokens per 1 day" in message

    # Test cost limit
    # Add requests totaling $49.00
    for _ in range(49):
        allowed, _ = quota_service.check_quota("gpt-4", "user2", "app2", 200, 1.00)
        assert allowed
        db_session.add(APIRequest(
            model="gpt-4",
            username="user2",
            caller_name="app2",
            input_tokens=200,
            output_tokens=500,
            cost=1.00,
            timestamp=datetime.now(timezone.utc)
        ))
        db_session.commit()

    # Check exceeding cost limit - should be blocked BEFORE adding
    allowed, message = quota_service.check_quota("gpt-4", "user2", "app2", 200, 1.01)
    assert not allowed
    assert "USER limit: 50.00 cost per 1 week" in message
