from datetime import datetime

import pytest

from llm_accounting.backends.base import UsageEntry, UsageStats


def test_usage_entry_creation():
    """Test UsageEntry creation with various parameters"""
    # Test with all parameters
    entry = UsageEntry(
        model="test-model",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        local_prompt_tokens=80,
        local_completion_tokens=40,
        local_total_tokens=120,
        cost=0.002,
        execution_time=1.5,
        timestamp=datetime(2024, 1, 1, 12, 0)
    )

    assert entry.model == "test-model"
    assert entry.prompt_tokens == 100
    assert entry.completion_tokens == 50
    assert entry.total_tokens == 150
    assert entry.local_prompt_tokens == 80
    assert entry.local_completion_tokens == 40
    assert entry.local_total_tokens == 120
    assert entry.cost == 0.002
    assert entry.execution_time == 1.5
    assert entry.timestamp == datetime(2024, 1, 1, 12, 0)
    assert entry.id is None # id is optional and defaults to None
    assert entry.cached_tokens == 0 # __post_init__ sets to 0 if None
    assert entry.reasoning_tokens == 0 # __post_init__ sets to 0 if None


    # Test with minimal parameters
    entry_minimal = UsageEntry(
        model="test-model",
        cost=0.002,
        execution_time=1.5
    )

    assert entry_minimal.model == "test-model"
    # These are set to 0 by __post_init__ if not provided
    assert entry_minimal.prompt_tokens == 0
    assert entry_minimal.completion_tokens == 0
    assert entry_minimal.total_tokens == 0
    assert entry_minimal.local_prompt_tokens == 0
    assert entry_minimal.local_completion_tokens == 0
    assert entry_minimal.local_total_tokens == 0
    assert entry_minimal.cached_tokens == 0
    assert entry_minimal.reasoning_tokens == 0
    assert entry_minimal.cost == 0.002
    assert entry_minimal.execution_time == 1.5
    assert isinstance(entry_minimal.timestamp, datetime)
    assert entry_minimal.id is None


def test_usage_stats_creation():
    """Test UsageStats creation with various parameters"""
    # Test with all parameters
    stats = UsageStats(
        sum_prompt_tokens=100,
        sum_completion_tokens=50,
        sum_total_tokens=150,
        sum_local_prompt_tokens=80,
        sum_local_completion_tokens=40,
        sum_local_total_tokens=120,
        sum_cost=0.002,
        sum_execution_time=1.5,
        avg_prompt_tokens=100,
        avg_completion_tokens=50,
        avg_total_tokens=150,
        avg_local_prompt_tokens=80,
        avg_local_completion_tokens=40,
        avg_local_total_tokens=120,
        avg_cost=0.002,
        avg_execution_time=1.5
    )

    assert stats.sum_prompt_tokens == 100
    assert stats.sum_completion_tokens == 50
    assert stats.sum_total_tokens == 150
    assert stats.sum_local_prompt_tokens == 80
    assert stats.sum_local_completion_tokens == 40
    assert stats.sum_local_total_tokens == 120
    assert stats.sum_cost == 0.002
    assert stats.sum_execution_time == 1.5
    assert stats.avg_prompt_tokens == 100
    assert stats.avg_completion_tokens == 50
    assert stats.avg_total_tokens == 150
    assert stats.avg_local_prompt_tokens == 80
    assert stats.avg_local_completion_tokens == 40
    assert stats.avg_local_total_tokens == 120
    assert stats.avg_cost == 0.002
    assert stats.avg_execution_time == 1.5

    # Test with default values
    stats = UsageStats()

    assert stats.sum_prompt_tokens == 0
    assert stats.sum_completion_tokens == 0
    assert stats.sum_total_tokens == 0
    assert stats.sum_local_prompt_tokens == 0
    assert stats.sum_local_completion_tokens == 0
    assert stats.sum_local_total_tokens == 0
    assert stats.sum_cost == 0.0
    assert stats.sum_execution_time == 0.0
    assert stats.avg_prompt_tokens == 0.0
    assert stats.avg_completion_tokens == 0.0
    assert stats.avg_total_tokens == 0.0
    assert stats.avg_local_prompt_tokens == 0.0
    assert stats.avg_local_completion_tokens == 0.0
    assert stats.avg_local_total_tokens == 0.0
    assert stats.avg_cost == 0.0
    assert stats.avg_execution_time == 0.0
