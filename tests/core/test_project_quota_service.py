import pytest
from datetime import datetime, timedelta, timezone
from llm_accounting import LLMAccounting, UsageEntry
from llm_accounting.models.limits import LimitScope, LimitType, TimeInterval, UsageLimit
from llm_accounting.services.quota_service import QuotaService
from llm_accounting.backends.sqlite import SQLiteBackend # Using real SQLite backend for these tests

@pytest.fixture
def sqlite_backend_for_quota(tmp_path):
    """Provides a clean SQLiteBackend instance for each test."""
    db_path = tmp_path / "test_quota_project.sqlite"
    backend = SQLiteBackend(db_path=str(db_path))
    with LLMAccounting(backend=backend) as acc: # Ensures tables are created
        acc.purge() # Clean slate
    return backend

@pytest.fixture
def accounting_for_quota(sqlite_backend_for_quota):
    """Provides an LLMAccounting instance with a clean SQLite backend."""
    with LLMAccounting(backend=sqlite_backend_for_quota) as acc:
        yield acc # acc.purge() is done by the backend fixture setup

# --- Helper to add usage ---
def add_usage(accounting_instance, model, cost, input_tokens, project_name=None, username="test_user", caller_name="test_caller", count=1):
    for _ in range(count):
        accounting_instance.track_usage(
            model=model,
            cost=cost,
            prompt_tokens=input_tokens, # Assuming input_tokens is representative for token limits
            project=project_name,
            username=username,
            caller_name=caller_name,
            timestamp=datetime.now(timezone.utc) # Ensure distinct timestamps if needed, or rely on ID
        )

# --- Project Scope Limit Tests ---

def test_project_limit_cost(accounting_for_quota: LLMAccounting):
    """Test cost limit scoped to a specific project."""
    project_a = "ProjectA"
    accounting_for_quota.set_usage_limit(
        scope=LimitScope.PROJECT,
        limit_type=LimitType.COST,
        max_value=5.0,
        interval_unit=TimeInterval.DAY,
        interval_value=1,
        project_name=project_a
    )

    # Usage for ProjectA
    add_usage(accounting_for_quota, model="gpt-4", cost=2.0, input_tokens=10, project_name=project_a, count=2) # Total cost 4.0
    allowed, _ = accounting_for_quota.check_quota(model="gpt-4", cost=1.0, input_tokens=10, project_name=project_a, username="user1", caller_name="app1")
    assert allowed, "Should be allowed, under project limit"

    add_usage(accounting_for_quota, model="gpt-4", cost=1.0, input_tokens=10, project_name=project_a) # Total cost 5.0
    allowed, message = accounting_for_quota.check_quota(model="gpt-4", cost=0.01, input_tokens=1, project_name=project_a, username="user1", caller_name="app1")
    assert not allowed, "Should be denied, project limit reached"
    assert message is not None
    assert f"PROJECT (project: {project_a}) limit: 5.00 cost per 1 day, current usage: 5.00, request: 0.01" in message

    # Usage for ProjectB (should not be affected by ProjectA's limit)
    project_b = "ProjectB"
    allowed, _ = accounting_for_quota.check_quota(model="gpt-4", cost=3.0, input_tokens=10, project_name=project_b, username="user1", caller_name="app1")
    assert allowed, "ProjectB usage should be allowed, not subject to ProjectA's limit"
    add_usage(accounting_for_quota, model="gpt-4", cost=3.0, input_tokens=10, project_name=project_b)


def test_project_limit_requests(accounting_for_quota: LLMAccounting):
    """Test request limit scoped to a specific project."""
    project_c = "ProjectC"
    accounting_for_quota.set_usage_limit(
        scope=LimitScope.PROJECT,
        limit_type=LimitType.REQUESTS,
        max_value=2.0, # Max 2 requests
        interval_unit=TimeInterval.DAY,
        interval_value=1,
        project_name=project_c
    )

    add_usage(accounting_for_quota, model="claude-2", cost=0.1, input_tokens=5, project_name=project_c, count=1)
    allowed, _ = accounting_for_quota.check_quota(model="claude-2", cost=0.1, input_tokens=5, project_name=project_c, username="user2", caller_name="app2")
    assert allowed, "Request 2 for ProjectC should be allowed"
    add_usage(accounting_for_quota, model="claude-2", cost=0.1, input_tokens=5, project_name=project_c, count=1) # Total 2 requests

    allowed, message = accounting_for_quota.check_quota(model="claude-2", cost=0.1, input_tokens=5, project_name=project_c, username="user2", caller_name="app2")
    assert not allowed, "Request 3 for ProjectC should be denied"
    assert message is not None
    assert f"PROJECT (project: {project_c}) limit: 2.00 requests per 1 day, current usage: 2.00, request: 1.00" in message

# --- Interaction with Global Limits ---

def test_project_limit_with_global_limit_cost(accounting_for_quota: LLMAccounting):
    """Test interaction between a project-specific cost limit and a global cost limit."""
    project_d = "ProjectD"
    # Global limit: 10.0 cost
    accounting_for_quota.set_usage_limit(LimitScope.GLOBAL, LimitType.COST, 10.0, TimeInterval.DAY, 1)
    # ProjectD limit: 5.0 cost
    accounting_for_quota.set_usage_limit(LimitScope.PROJECT, LimitType.COST, 5.0, TimeInterval.DAY, 1, project_name=project_d)

    # Use 4.0 cost for ProjectD (allowed by both project and global)
    add_usage(accounting_for_quota, model="gpt-4", cost=2.0, input_tokens=10, project_name=project_d, count=2)
    allowed, _ = accounting_for_quota.check_quota(model="gpt-4", cost=1.0, input_tokens=10, project_name=project_d, username="user1", caller_name="app1")
    assert allowed, "ProjectD should be allowed (cost 4.0 + 1.0 = 5.0, project limit)"

    add_usage(accounting_for_quota, model="gpt-4", cost=1.0, input_tokens=10, project_name=project_d) # ProjectD total cost = 5.0

    # Next request for ProjectD should be denied by ProjectD's limit
    allowed, message = accounting_for_quota.check_quota(model="gpt-4", cost=0.1, input_tokens=1, project_name=project_d, username="user1", caller_name="app1")
    assert not allowed, "ProjectD should be denied by its own limit"
    assert message is not None
    assert f"PROJECT (project: {project_d}) limit: 5.00 cost per 1 day, current usage: 5.00, request: 0.10" in message

    # Use 6.0 cost for ProjectE (ProjectD is at 5.0, Global is at 5.0 + this 6.0 = 11.0)
    # This should be denied by the Global limit
    project_e = "ProjectE"
    add_usage(accounting_for_quota, model="gpt-4", cost=3.0, input_tokens=10, project_name=project_e, count=1) # ProjectE cost 3.0, Global 5.0+3.0=8.0
    allowed, _ = accounting_for_quota.check_quota(model="gpt-4", cost=1.0, input_tokens=10, project_name=project_e, username="user1", caller_name="app1")
    assert allowed # ProjectE cost 4.0, Global 5.0+4.0=9.0

    add_usage(accounting_for_quota, model="gpt-4", cost=1.0, input_tokens=10, project_name=project_e) # ProjectE cost 4.0

    allowed, message = accounting_for_quota.check_quota(model="gpt-4", cost=1.1, input_tokens=10, project_name=project_e, username="user1", caller_name="app1")
    # ProjectD=5.0, ProjectE=4.0. Global usage = 9.0. Requesting 1.1 for ProjectE.
    # Total global would be 10.1, exceeding global limit of 10.0
    assert not allowed, "ProjectE should be denied by the global limit"
    assert message is not None
    assert f"GLOBAL limit: 10.00 cost per 1 day, current usage: 9.00, request: 1.10" in message


def test_project_limit_with_model_limit(accounting_for_quota: LLMAccounting):
    """Test interaction between project limit and model limit."""
    project_f = "ProjectF"
    model_name = "special-model"

    # Model limit for "special-model": 3 requests
    accounting_for_quota.set_usage_limit(LimitScope.MODEL, LimitType.REQUESTS, 3, TimeInterval.DAY, 1, model=model_name)
    # ProjectF limit for "special-model": 2 requests
    accounting_for_quota.set_usage_limit(LimitScope.PROJECT, LimitType.REQUESTS, 2, TimeInterval.DAY, 1, model=model_name, project_name=project_f)

    # Request 1 for special-model in ProjectF (allowed)
    add_usage(accounting_for_quota, model=model_name, cost=0.1, input_tokens=1, project_name=project_f)
    allowed, _ = accounting_for_quota.check_quota(model=model_name, cost=0.1, input_tokens=1, project_name=project_f, username="u", caller_name="c")
    assert allowed

    # Request 2 for special-model in ProjectF (allowed by project, hits project limit)
    add_usage(accounting_for_quota, model=model_name, cost=0.1, input_tokens=1, project_name=project_f)
    allowed, message = accounting_for_quota.check_quota(model=model_name, cost=0.1, input_tokens=1, project_name=project_f, username="u", caller_name="c")
    assert not allowed, "Should be denied by ProjectF limit"
    assert message is not None
    assert f"PROJECT (model: {model_name}, project: {project_f}) limit: 2.00 requests per 1 day, current usage: 2.00, request: 1.00" in message

    # Request for special-model in ProjectG (ProjectF limit doesn't apply)
    project_g = "ProjectG"
    # This is the 3rd request for "special-model" overall.
    add_usage(accounting_for_quota, model=model_name, cost=0.1, input_tokens=1, project_name=project_g)
    allowed, message = accounting_for_quota.check_quota(model=model_name, cost=0.1, input_tokens=1, project_name=project_g, username="u", caller_name="c")
    assert not allowed, "3rd request for special-model (in ProjectG) should be denied by model limit"
    assert message is not None
    assert f"MODEL (model: {model_name}) limit: 3.00 requests per 1 day, current usage: 3.00, request: 1.00" in message

def test_project_limit_with_no_specific_project_in_request(accounting_for_quota: LLMAccounting):
    """Test that a request with no project is not affected by a project-specific limit."""
    project_h = "ProjectH"
    accounting_for_quota.set_usage_limit(
        scope=LimitScope.PROJECT,
        limit_type=LimitType.COST,
        max_value=1.0,
        interval_unit=TimeInterval.DAY,
        interval_value=1,
        project_name=project_h
    )
    # This request has no project, so ProjectH's limit should not apply.
    allowed, _ = accounting_for_quota.check_quota(model="gpt-4", cost=2.0, input_tokens=10, project_name=None, username="user1", caller_name="app1")
    assert allowed, "Request with no project should not be affected by ProjectH's limit"

    # Add usage to ProjectH to hit its limit
    add_usage(accounting_for_quota, model="gpt-4", cost=1.0, input_tokens=10, project_name=project_h)
    allowed, _ = accounting_for_quota.check_quota(model="gpt-4", cost=0.1, input_tokens=1, project_name=project_h, username="user1", caller_name="app1")
    assert not allowed, "ProjectH should now be over limit"

    # Another request with no project should still be allowed
    allowed, _ = accounting_for_quota.check_quota(model="gpt-4", cost=2.0, input_tokens=10, project_name=None, username="user1", caller_name="app1")
    assert allowed, "Request with no project should still be allowed even if ProjectH is over limit"

def test_limit_message_for_project_scope(accounting_for_quota: LLMAccounting):
    """Test the limit exhaustion message for project-scoped limits."""
    project_name = "DetailProject"
    model_name = "detailed-model"
    accounting_for_quota.set_usage_limit(
        scope=LimitScope.PROJECT,
        limit_type=LimitType.REQUESTS,
        max_value=1,
        interval_unit=TimeInterval.DAY,
        interval_value=1,
        project_name=project_name,
        model=model_name # Also associate with a model for more specific message
    )
    add_usage(accounting_for_quota, model=model_name, cost=0.1, input_tokens=1, project_name=project_name)
    allowed, message = accounting_for_quota.check_quota(model=model_name, cost=0.1, input_tokens=1, project_name=project_name, username="u", caller_name="c")
    
    assert not allowed
    assert message is not None
    assert f"PROJECT (model: {model_name}, project: {project_name}) limit: 1.00 requests per 1 day, current usage: 1.00, request: 1.00" in message
