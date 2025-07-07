from llm_accounting import LLMAccounting
from llm_accounting.models.limits import (LimitScope, LimitType, TimeInterval)


def test_cache_rebuild_after_inserting_limit(memory_sqlite_backend):
    accounting = LLMAccounting(backend=memory_sqlite_backend)
    # Define request parameters
    model = "test-model-insert"
    username = "test-user-insert"
    caller_name = "test-caller-insert"
    project_name = "test-project-insert"
    input_tokens = 100
    cost = 1.0

    # 1. Initial check (should be allowed)
    allowed, reason = accounting.check_quota(
        model=model,
        username=username,
        caller_name=caller_name,
        project_name=project_name,
        input_tokens=input_tokens,
        cost=cost
    )
    assert allowed is True, f"Initial check should be allowed, but was denied: {reason}"

    # 2. Insert a restrictive limit
    accounting.set_usage_limit(
        scope=LimitScope.USER,
        limit_type=LimitType.COST,
        max_value=0.5, # Restrictive limit
        interval_unit=TimeInterval.DAY,
        interval_value=1,
        username=username
    )

    # 3. Check again (should be denied due to new limit)
    allowed, reason = accounting.check_quota(
        model=model,
        username=username,
        caller_name=caller_name,
        project_name=project_name,
        input_tokens=input_tokens,
        cost=cost
    )
    assert allowed is False, "Check after inserting limit should be denied"
    assert reason is not None, "Reason for denial should not be None"
    # Example of a more specific reason check, adapt if necessary
    assert f"USER (user: {username}) limit: 0.50 cost per 1 day exceeded." in reason

    # 4. Clean up: Find and delete the limit
    limits = accounting.get_usage_limits(username=username, scope=LimitScope.USER)
    limit_deleted = False
    for limit in limits:
        if limit.limit_type == LimitType.COST.value and limit.max_value == 0.5 and limit.username == username: # Identify the specific limit
            accounting.delete_usage_limit(limit.id)
            limit_deleted = True
            break
    assert limit_deleted, "Could not find the test limit to delete"


def test_cache_rebuild_after_deleting_limit(memory_sqlite_backend):
    accounting = LLMAccounting(backend=memory_sqlite_backend)
    model = "test-model-deletion"
    username = "test-user-deletion"
    caller_name = "test-caller-deletion"
    project_name = "test-project-deletion"
    input_tokens = 10
    cost = 0.1

    # 1. Insert a restrictive limit first
    accounting.set_usage_limit(
        scope=LimitScope.USER,
        limit_type=LimitType.INPUT_TOKENS,
        max_value=5, # Restrictive
        interval_unit=TimeInterval.HOUR,
        interval_value=1,
        username=username
    )

    # Verify it's active
    allowed, reason = accounting.check_quota(model, username, caller_name, input_tokens, cost, project_name=project_name)
    assert allowed is False, f"Request should be denied by the new limit: {reason}"

    # 2. Find and delete the limit
    limits = accounting.get_usage_limits(username=username, scope=LimitScope.USER)
    limit_id_to_delete = None
    for limit_obj in limits:
        if limit_obj.limit_type == LimitType.INPUT_TOKENS.value and limit_obj.max_value == 5 and limit_obj.username == username:
            limit_id_to_delete = limit_obj.id
            break
    assert limit_id_to_delete is not None, "Test limit was not found for deletion"

    accounting.delete_usage_limit(limit_id_to_delete)

    # 3. Check again (should be allowed as the limit is gone)
    allowed, reason = accounting.check_quota(model, username, caller_name, input_tokens, cost, project_name=project_name)
    assert allowed is True, f"Request should be allowed after deleting limit, but was denied: {reason}"
